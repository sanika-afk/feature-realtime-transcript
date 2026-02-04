"""
Recall AI WebSocket receiver for real-time meeting analysis.
- POST /bot: Create a Recall bot that streams via WebSocket (needs PUBLIC_WS_URL).
- /ws/recall: Recall.ai connects here and pushes video/audio/transcript events.
- /ws/analysis: Dashboard clients connect to receive real-time analysis from OpenAI.
- GET /stats: Returns counts of received events (for testing video/audio streams).
"""
import asyncio
import base64
import json
import logging
import time
from typing import Optional, Set, Any, Dict, List
from collections import deque

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, HTTPException, status
from fastapi.responses import StreamingResponse, HTMLResponse
from fastapi.requests import Request

from app.config import settings
from app.models import CreateBotRequest, BotResponse
from app.recall_client import RecallAIClient
from app.routes.bots import parse_meeting_url

from app.openai_client import OpenAIClient

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/live", tags=["live"])
recall_client = RecallAIClient()

# Subscribers that receive real-time analysis (e.g. dashboard)
_analysis_subscribers: Set[WebSocket] = set()

# Last received frame (PNG or JPEG bytes) and transcript
_frame_queue: asyncio.Queue = asyncio.Queue(maxsize=5)
_transcript_queue: asyncio.Queue = asyncio.Queue(maxsize=50)

# One active Recall connection per "session"
_recall_ws: Optional[WebSocket] = None

# Stream stats: event counts and last event time (for testing)
_stream_stats: Dict[str, Any] = {
    "connected": False,
    "events": {},
    "last_event_at": None,
    "last_event_type": None,
}

# Latest video frame from Recall (for MJPEG / HTML viewer)
_latest_frame: Optional[bytes] = None
_latest_frame_mime: str = "image/png"  # Recall sends PNG

# Compliance analysis state
_recent_frames: deque = deque(maxlen=20)   # Buffer of recent frames
_transcript_buffer: List[str] = []         # Buffer for partial transcript snippets
_openai_client: Optional[OpenAIClient] = None
_latest_analysis: Optional[Dict[str, Any]] = None

if settings.OPENAI_API_KEY:
    try:
        _openai_client = OpenAIClient()
        logger.info("[LIVE] OpenAIClient initialized for background compliance analysis.")
        logger.info("[LIVE] Using model: %s", _openai_client.model_id)
    except Exception as e:
        logger.error("[LIVE] Failed to initialize OpenAIClient: %s", e)
else:
    logger.warning("[LIVE] OPENAI_API_KEY is missing! OpenAI analysis will not run.")


async def _broadcast_analysis(data: dict) -> None:
    """Send analysis JSON to all subscribed clients."""
    if not _analysis_subscribers:
        return
    msg = json.dumps(data)
    dead = set()
    for ws in _analysis_subscribers:
        try:
            await ws.send_text(msg)
        except Exception:
            dead.add(ws)
    for ws in dead:
        _analysis_subscribers.discard(ws)


def _record_stream_event(event: str) -> None:
    """Record that we received an event (for GET /stats)."""
    global _stream_stats
    events = _stream_stats["events"]
    events[event] = events.get(event, 0) + 1
    _stream_stats["last_event_at"] = time.time()
    _stream_stats["last_event_type"] = event
    # Log every 50th event per type to avoid spam (DEBUG level)
    if events[event] % 50 == 1:
        logger.debug("Recall stream: %s count=%d", event, events[event])


MJPEG_BOUNDARY = "frame"


async def _mjpeg_generator():
    """Yield MJPEG stream (multipart/x-mixed-replace) of latest frames."""
    global _latest_frame, _latest_frame_mime
    last_sent: Optional[bytes] = None
    while True:
        frame = _latest_frame
        if frame and frame != last_sent:
            last_sent = frame
            mime = _latest_frame_mime
            part = (
                f"--{MJPEG_BOUNDARY}\r\n"
                f"Content-Type: {mime}\r\n"
                f"Content-Length: {len(frame)}\r\n\r\n"
            ).encode("utf-8") + frame + b"\r\n"
            yield part
        await asyncio.sleep(0.2)


@router.get("/stream", response_class=StreamingResponse)
async def stream_video():
    """
    MJPEG stream of the latest Recall video frame.
    Use in HTML: <img src="/api/live/stream" />
    """
    return StreamingResponse(
        _mjpeg_generator(),
        media_type=f"multipart/x-mixed-replace; boundary={MJPEG_BOUNDARY}",
    )


@router.get("/view", response_class=HTMLResponse)
async def view_stream_page(request: Request):
    """HTML page that displays the live Recall video stream (MJPEG) and stats."""
    base = request.base_url
    # Use relative path so it works behind proxies
    stream_url = str(base).rstrip("/") + "/api/live/stream"
    stats_url = str(base).rstrip("/") + "/api/live/stats"
    html = _viewer_html(stream_url=stream_url, stats_url=stats_url)
    return HTMLResponse(html)


def _viewer_html(stream_url: str, stats_url: str) -> str:
    return """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Live Meeting Analysis - OpenAI</title>
    <style>
        * { box-sizing: border-box; }
        body { font-family: 'Inter', system-ui, sans-serif; margin: 0; background: #0a0a0c; color: #f0f0f5; padding: 2rem; display: grid; grid-template-columns: 1fr 350px; gap: 2rem; height: 100vh; }
        .main-content { overflow: hidden; display: flex; flex-direction: column; gap: 1rem; }
        .sidebar { background: #16161d; border-radius: 12px; padding: 1.5rem; display: flex; flex-direction: column; gap: 1.5rem; overflow-y: auto; border: 1px solid #2d2d3d; }
        h1 { margin: 0; font-size: 1.5rem; background: linear-gradient(90deg, #60a5fa, #a78bfa); -webkit-background-clip: text; -webkit-text-fill-color: transparent; }
        .video-wrap { background: #000; border-radius: 12px; overflow: hidden; border: 1px solid #2d2d3d; flex-grow: 1; display: flex; align-items: center; justify-content: center; position: relative; }
        .video-wrap img { width: 100%; height: 100%; object-fit: contain; }
        .overlay { position: absolute; top: 1rem; right: 1rem; }
        .badge { padding: 0.4rem 0.8rem; border-radius: 20px; font-weight: 600; font-size: 0.8rem; text-transform: uppercase; letter-spacing: 0.05em; }
        .badge.connected { background: rgba(34, 197, 94, 0.2); color: #4ade80; border: 1px solid #22c55e; }
        .badge.disconnected { background: rgba(239, 68, 68, 0.2); color: #f87171; border: 1px solid #ef4444; }
        .analysis-card { background: #1f1f29; border-radius: 10px; padding: 1rem; border-left: 4px solid #60a5fa; }
        .analysis-card h3 { margin: 0 0 0.5rem 0; font-size: 0.9rem; color: #94a3b8; text-transform: uppercase; }
        .status-compliant { border-left-color: #22c55e; }
        .status-violation { border-left-color: #ef4444; }
        .stat-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 1rem; margin-top: 1rem; }
        .stat-item { background: #0f172a; padding: 0.75rem; border-radius: 8px; text-align: center; }
        .stat-value { font-size: 1.25rem; font-weight: 700; color: #fff; }
        .stat-label { font-size: 0.7rem; color: #94a3b8; margin-top: 0.25rem; }
        .transcript-box { background: #0f172a; padding: 1rem; border-radius: 8px; font-size: 0.9rem; line-height: 1.5; color: #cbd5e1; font-style: italic; max-height: 150px; overflow-y: auto; position: relative; }
        .partial-flag { font-size: 0.6rem; color: #60a5fa; position: absolute; top: 0.5rem; right: 0.5rem; text-transform: uppercase; letter-spacing: 0.05em; font-weight: bold; }
        .summary-box { background: #1e293b; padding: 1rem; border-radius: 8px; margin-top: 1rem; font-size: 0.9rem; border-top: 2px solid #60a5fa; }
        .noise-alert { background: rgba(239, 68, 68, 0.1); border: 1px solid #ef4444; color: #f87171; padding: 0.5rem; border-radius: 6px; font-size: 0.8rem; margin-top: 0.5rem; display: none; }
        pre { background: #000; padding: 1rem; border-radius: 8px; font-size: 0.75rem; color: #64748b; overflow-x: auto; margin: 0; }
        @media (max-width: 1000px) { body { grid-template-columns: 1fr; height: auto; } .sidebar { height: 500px; } }
    </style>
</head>
<body>
    <div class="main-content">
        <div style="display: flex; justify-content: space-between; align-items: center;">
            <h1>Universal Meeting Bot Live</h1>
            <span id="status" class="badge disconnected">Disconnected</span>
        </div>
        <div class="video-wrap">
            <img id="stream" src="" alt="Meeting Stream" />
        </div>
        <div class="analysis-card" id="latest-transcript-card">
            <h3>Transcript Feed <span id="transcript-type" class="partial-flag"></span></h3>
            <div id="latest-transcript" class="transcript-box">Waiting for audio...</div>
            <div id="noise-alert" class="noise-alert">⚠ NOISE DETECTED: <span id="noise-desc"></span></div>
        </div>
        <div class="summary-box" id="discussion-summary-box" style="display: none;">
            <h3 style="font-size: 0.8rem; color: #94a3b8; margin: 0 0 0.5rem 0; text-transform: uppercase;">Discussion Insight</h3>
            <div id="discussion-summary" style="line-height: 1.4; color: #e2e8f0;"></div>
        </div>
    </div>
    
    <div class="sidebar">
        <div class="analysis-card" id="compliance-card">
            <h3>OpenAI Analysis</h3>
            <div id="compliance-status" style="font-size: 1.2rem; font-weight: bold; margin-bottom: 0.5rem;">Waiting for frames...</div>
            <div id="compliance-notes" style="font-size: 0.85rem; color: #94a3b8;">Analysis will appear as the meeting progresses.</div>
            
            <div class="stat-grid">
                <div class="stat-item">
                    <div class="stat-value" id="person-count">--</div>
                    <div class="stat-label">Person Count</div>
                </div>
                <div class="stat-item">
                    <div class="stat-value" id="security-score">--</div>
                    <div class="stat-label">Compliance Score</div>
                </div>
            </div>
            
            <div id="professionalism-info" style="margin-top: 1rem; font-size: 0.8rem;">
                <div id="prof-badge" style="display: inline-block; padding: 0.2rem 0.5rem; border-radius: 4px; font-weight: bold; margin-bottom: 0.3rem;"></div>
                <div id="prof-note" style="color: #94a3b8;"></div>
            </div>
        </div>

        <div>
            <h3 style="font-size: 0.8rem; color: #64748b; margin-bottom: 0.5rem;">Raw Stream Stats</h3>
            <pre id="stats">Connecting to stats API...</pre>
        </div>
    </div>

    <script>
        const streamUrl = """ + json.dumps(stream_url) + """;
        const statsUrl = """ + json.dumps(stats_url) + """;
        const img = document.getElementById("stream");
        const statusEl = document.getElementById("status");
        const statsEl = document.getElementById("stats");
        
        img.src = streamUrl;
        img.onload = () => { statusEl.textContent = "Stream Active"; statusEl.className = "badge connected"; };
        img.onerror = () => { statusEl.textContent = "No Frames"; statusEl.className = "badge disconnected"; };

        async function refreshStats() {
            try {
                const r = await fetch(statsUrl);
                const j = await r.json();
                
                // Update raw stats display
                statsEl.textContent = JSON.stringify({events: j.events, last_event: j.last_event_type}, null, 2);
                
                // Update Badge
                if (j.connected) {
                    statusEl.textContent = "Connected • " + (j.last_event_type || "Active");
                    statusEl.className = "badge connected";
                } else {
                    statusEl.textContent = "Disconnected";
                    statusEl.className = "badge disconnected";
                }

                // Update OpenAI Analysis results if available
                if (j.latest_analysis) {
                    updateAnalysisUI(j.latest_analysis);
                }

            } catch (e) { statsEl.textContent = "Error: " + e.message; }
        }

        function updateAnalysisUI(data) {
            const analysis = data.analysis;
            const transcript = data.transcript;
            
            document.getElementById("latest-transcript").textContent = '"' + transcript + '"';
            document.getElementById("transcript-type").textContent = data.is_partial ? "Real-time" : "Final";
            
            if (analysis && !analysis.error) {
                // Core scores
                const score = analysis.hipaa_compliance?.compliance_score || 0;
                document.getElementById("person-count").textContent = analysis.person_count || "0";
                document.getElementById("security-score").textContent = score + "%";
                
                const statusEl = document.getElementById("compliance-status");
                const cardEl = document.getElementById("compliance-card");
                
                if (score >= 80) {
                    statusEl.textContent = "✅ COMPLIANT";
                    statusEl.style.color = "#4ade80";
                    cardEl.className = "analysis-card status-compliant";
                } else {
                    statusEl.textContent = "⚠ ATTENTION REQUIRED";
                    statusEl.style.color = "#f87171";
                    cardEl.className = "analysis-card status-violation";
                }
                
                let notes = "";
                if (analysis.hipaa_compliance?.violations?.length > 0) {
                    notes = "Issues: " + analysis.hipaa_compliance.violations.join(", ");
                } else {
                    notes = "No violations detected in the last analyzed frame.";
                }
                document.getElementById("compliance-notes").textContent = notes;

                // Enhanced fields: Professionalism
                const profBadge = document.getElementById("prof-badge");
                const env = analysis.environment_analysis;
                if (env) {
                    profBadge.textContent = env.is_professional ? "PROFESSIONAL" : "NON-PROFESSIONAL";
                    profBadge.style.background = env.is_professional ? "rgba(34, 197, 94, 0.2)" : "rgba(245, 158, 11, 0.2)";
                    profBadge.style.color = env.is_professional ? "#4ade80" : "#fbbf24";
                    document.getElementById("prof-note").textContent = env.professionalism_note || "";
                }

                // Enhanced fields: Summary
                if (analysis.discussion_summary) {
                    document.getElementById("discussion-summary-box").style.display = "block";
                    document.getElementById("discussion-summary").textContent = analysis.discussion_summary;
                }

                // Enhanced fields: Noise
                const noiseAlert = document.getElementById("noise-alert");
                if (analysis.noise_detection?.detected) {
                    noiseAlert.style.display = "block";
                    document.getElementById("noise-desc").textContent = analysis.noise_detection.description;
                } else {
                    noiseAlert.style.display = "none";
                }
            }
        }
        
        refreshStats();
        setInterval(refreshStats, 3000);
    </script>
</body>
</html>"""


@router.get("/stats")
async def get_stream_stats() -> Dict[str, Any]:
    """
    Return counts of events received from Recall on the WebSocket.
    Use this to verify video/audio/transcript streams are flowing.
    """
    return {
        "connected": _stream_stats["connected"],
        "events": dict(_stream_stats["events"]),
        "last_event_at": _stream_stats["last_event_at"],
        "last_event_type": _stream_stats["last_event_type"],
        "latest_analysis": _latest_analysis
    }


def _decode_frame_from_event(data: Any) -> Optional[bytes]:
    """Extract image bytes from Recall event data (e.g. video_separate_png.data).
    Recall sends: data.buffer (base64) or data.data (base64); fallback to top-level or raw string.
    """
    if data is None:
        return None
    inner = data.get("data") if isinstance(data, dict) else data
    if isinstance(inner, str):
        try:
            return base64.b64decode(inner)
        except Exception:
            return None
    if isinstance(inner, dict):
        buf = inner.get("buffer") or inner.get("data") or inner.get("image") or inner.get("frame")
        if buf is None:
            return None
        if isinstance(buf, str):
            try:
                return base64.b64decode(buf)
            except Exception:
                return None
        if isinstance(buf, bytes):
            return buf
    # Top-level buffer (e.g. data.buffer when data is the whole payload)
    if isinstance(data, dict):
        buf = data.get("buffer") or data.get("data")
        if isinstance(buf, str):
            try:
                return base64.b64decode(buf)
            except Exception:
                pass
        if isinstance(buf, bytes):
            return buf
    return None


async def _run_openai_analysis(text: str, frame: bytes) -> None:
    """Run structured compliance analysis using OpenAI on a sentence + frame and broadcast."""
    logger.info("[COMPLIANCE-OPENAI] _run_openai_analysis called with text: %s", text[:50])
    if not _openai_client:
        logger.warning("[COMPLIANCE-OPENAI] OpenAIClient not available; skipping analysis.")
        return

    logger.info("[COMPLIANCE-OPENAI] Starting analysis for sentence: %s...", text[:50])
    try:
        # Detect MIME type
        mime = "image/png" if frame.startswith(b"\x89PNG") else "image/jpeg"
        
        # Call OpenAI analysis
        analysis = await _openai_client.analyze_frame(frame, audio_transcript=text, mime_type=mime)
        
        # Store for the REST stats / HTML viewer
        global _latest_analysis
        _latest_analysis = {
            "transcript": text,
            "analysis": analysis,
            "is_partial": False,
            "timestamp": time.time()
        }

        # Broadcast the structured result to the dashboard
        await _broadcast_analysis({
            "event": "compliance_analysis",
            "data": _latest_analysis
        })
        logger.info("[COMPLIANCE-OPENAI] Analysis broadcasted.")
    except Exception as e:
        logger.error("[COMPLIANCE-OPENAI] Analysis failed: %s", e)
        await _broadcast_analysis({
            "event": "compliance_error",
            "data": {"error": str(e), "transcript": text}
        })


@router.post("/bot", response_model=BotResponse, status_code=status.HTTP_201_CREATED)
async def create_bot_live(request: CreateBotRequest):
    """
    Create a Recall bot that streams real-time video/audio/transcript via WebSocket.
    Recall will connect to PUBLIC_WS_URL + /api/live/ws/recall.
    Set PUBLIC_WS_URL in env (e.g. wss://your-domain.com) so Recall can reach your server.
    """
    if not settings.PUBLIC_WS_URL:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="PUBLIC_WS_URL must be set (e.g. wss://your-domain.com) for WebSocket bot",
        )
    base = settings.PUBLIC_WS_URL.rstrip("/")
    websocket_url = f"{base}/api/live/ws/recall"
    try:
        bot_data = await recall_client.create_bot_with_websocket(
            meeting_url=str(request.meeting_url),
            websocket_url=websocket_url,
            video_layout=request.video_layout,
            auto_leave=request.auto_leave,
            bot_name=request.bot_name,
            events=request.events,
        )
        meeting_url_str, meeting_metadata = parse_meeting_url(
            bot_data.get("meeting_url"),
            bot_data.get("meeting_metadata") or {},
        )
        return BotResponse(
            id=bot_data.get("id"),
            status=bot_data.get("status", "unknown"),
            bot_name=bot_data.get("bot_name"),
            stream_key=None,
            meeting_url=meeting_url_str,
            meeting_metadata=meeting_metadata,
            created_at=bot_data.get("created_at"),
            error_message=bot_data.get("error_message"),
        )
    except Exception as e:
        detail = str(e)
        if hasattr(e, "response") and e.response is not None:
            try:
                err_body = e.response.json()
                detail = f"Recall API error: {err_body}"
            except Exception:
                detail = f"Recall API error: {e.response.text if hasattr(e.response, 'text') else detail}"
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=detail,
        )


@router.websocket("/ws/recall")
async def websocket_recall(websocket: WebSocket) -> None:
    """
    Recall.ai connects to this endpoint (use PUBLIC_WS_URL when creating the bot).
    Receives events: video_separate_png.data, transcript.data, audio_mixed_raw.data, etc.
    Frames and transcripts are processed for OpenAI analysis.
    """
    global _recall_ws, _stream_stats
    logger.info("Recall WebSocket: connection attempt received")
    try:
        await websocket.accept()
    except Exception as e:
        logger.exception("Recall WebSocket: accept failed: %s", e)
        raise
    _recall_ws = websocket
    _stream_stats["connected"] = True
    _stream_stats["events"] = {}
    logger.info("[LIVE] Recall WebSocket connected.")
    try:
        while True:
            try:
                raw = await websocket.receive_text()
                try:
                    msg = json.loads(raw)
                except json.JSONDecodeError:
                    if isinstance(raw, bytes):
                        _frame_queue.put_nowait(raw)
                    continue
                
                event = msg.get("event") or msg.get("event_type")
                data = msg.get("data") or msg
                if not event:
                    continue
                
                _record_stream_event(event)

                if event in ("video_separate_png.data", "video_mixed_flv.data"):
                    frame = _decode_frame_from_event(data)
                    if frame:
                        global _latest_frame, _latest_frame_mime
                        _latest_frame = frame
                        _latest_frame_mime = "image/png" if event == "video_separate_png.data" else "image/jpeg"
                        _recent_frames.append(frame)  # Keep for compliance selection
                        try:
                            _frame_queue.put_nowait(frame)
                        except asyncio.QueueFull:
                            _frame_queue.get_nowait()
                            _frame_queue.put_nowait(frame)
                        # Log so we know frames are reaching the bridge (first + every 50th)
                        n = _stream_stats["events"].get(event, 0)
                        if n == 1 or n % 50 == 0:
                            logger.debug("[GEMINI-BRIDGE] Video frame queued (%d bytes, %s #%d)", len(frame), event, n)
                    else:
                        # Decode failed — log first and every 100th so we can fix payload handling
                        n = _stream_stats["events"].get(event, 0)
                        if n <= 1 or n % 100 == 0:
                            keys = list(data.keys()) if isinstance(data, dict) else type(data).__name__
                            logger.warning("[GEMINI-BRIDGE] Failed to decode video (event #%s). data keys: %s", n, keys)
                
                elif event == "audio_mixed_raw.data":
                    # Audio received (counted above). Optionally forward to bridge later.
                    pass
                
                elif event in ("transcript.data", "transcript.partial_data"):
                    inner = data.get("data") if isinstance(data, dict) and "data" in data else data
                    text = None
                    if isinstance(inner, dict):
                        text = inner.get("text") or inner.get("transcript") or inner.get("utterance")
                        if text is None and inner.get("words"):
                            text = " ".join(w.get("text", "") for w in inner["words"])
                    elif isinstance(inner, str):
                        text = inner
                    
                    if text:
                        if event == "transcript.partial_data":
                            # Log partials at INFO level for terminal visibility as requested
                            logger.info("[TRANSCRIPT] Real-time: %s", text)
                            print(f"\r[TRANSCRIPT] {text}", end="", flush=True) 
                            _transcript_buffer.append(text)
                            
                            # Update latest analysis state for polling clients
                            global _latest_analysis
                            _latest_analysis = {
                                "transcript": text,
                                "analysis": _latest_analysis.get("analysis") if _latest_analysis else None,
                                "is_partial": True,
                                "timestamp": time.time()
                            }
                            
                            # Broadcast partial transcript in real-time
                            await _broadcast_analysis({
                                "event": "transcript_update",
                                "data": _latest_analysis
                            })
                        else:  # transcript.data (Final utterance)
                            print(f"\n[TRANSCRIPT] Final: {text}")
                            full_sentence = " ".join(_transcript_buffer + [text])
                            _transcript_buffer.clear()
                            
                            logger.info("[TRANSCRIPT] Final: %s", full_sentence)
                            
                            # Trigger compliance analysis if we have a frame
                            logger.info("[COMPLIANCE] Final transcript received. Buffer size: %d frames.", len(_recent_frames))
                            if _recent_frames:
                                # Use the most recent frame as the representative one
                                rep_frame = _recent_frames[-1]
                                logger.info("[COMPLIANCE] Triggering OpenAI analysis task for: %s", full_sentence[:50])
                                asyncio.create_task(_run_openai_analysis(full_sentence, rep_frame))
                            else:
                                logger.warning("[COMPLIANCE] No frames available in buffer for analysis.")
                            
                            # Still push to the continuous bridge queue
                            try:
                                _transcript_queue.put_nowait(full_sentence)
                            except asyncio.QueueFull:
                                _transcript_queue.get_nowait()
                                _transcript_queue.put_nowait(full_sentence)
            except Exception as e:
                logger.exception("Error in Recall WebSocket message loop: %s", e)
                print(f"Error in Recall WebSocket loop: {e}")
                break
    except WebSocketDisconnect:
        logger.info("Recall WebSocket disconnected")
    except Exception as e:
        logger.exception("Recall WebSocket error: %s", e)
    finally:
        _recall_ws = None
        _stream_stats["connected"] = False
        
        # Signal queues to stop by putting None (and handle full queue)
        try:
            _frame_queue.put_nowait(None)
        except Exception:
            # If full or any other error, clear one and try once more
            try:
                if not _frame_queue.empty():
                    _frame_queue.get_nowait()
                _frame_queue.put_nowait(None)
            except Exception:
                pass

        try:
            _transcript_queue.put_nowait(None)
        except Exception:
            try:
                if not _transcript_queue.empty():
                    _transcript_queue.get_nowait()
                _transcript_queue.put_nowait(None)
            except Exception:
                pass


@router.websocket("/ws/analysis")
async def websocket_analysis(websocket: WebSocket) -> None:
    """Clients (e.g. dashboard) connect here to receive real-time analysis from Gemini Live."""
    await websocket.accept()
    _analysis_subscribers.add(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        _analysis_subscribers.discard(websocket)
