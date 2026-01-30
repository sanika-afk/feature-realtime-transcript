"""
Recall AI WebSocket receiver and bridge to Gemini Multimodal Live API.
- POST /bot: Create a Recall bot that streams via WebSocket (needs PUBLIC_WS_URL).
- /ws/recall: Recall.ai connects here and pushes video/audio/transcript events.
- /ws/analysis: Dashboard clients connect to receive real-time analysis from Gemini Live.
- GET /stats: Returns counts of received events (for testing video/audio streams).
"""
import asyncio
import base64
import json
import logging
import time
from typing import Optional, Set, Any, Dict

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, HTTPException, status
from fastapi.responses import StreamingResponse, HTMLResponse
from fastapi.requests import Request

from app.config import settings
from app.models import CreateBotRequest, BotResponse
from app.recall_client import RecallAIClient
from app.routes.bots import parse_meeting_url

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/live", tags=["live"])
recall_client = RecallAIClient()

# Subscribers that receive real-time analysis (e.g. dashboard)
_analysis_subscribers: Set[WebSocket] = set()

# Last received frame (PNG or JPEG bytes) and transcript - consumed by Gemini Live bridge at 1 FPS
_frame_queue: asyncio.Queue = asyncio.Queue(maxsize=5)
_transcript_queue: asyncio.Queue = asyncio.Queue(maxsize=50)

# One active Recall connection per "session"; bridge runs while connected
_recall_ws: Optional[WebSocket] = None
_bridge_task: Optional[asyncio.Task] = None

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
    # Log every 50th event per type to avoid spam
    if events[event] % 50 == 1:
        logger.info("Recall stream: %s count=%d", event, events[event])


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
    <title>Live Recall Stream</title>
    <style>
        * { box-sizing: border-box; }
        body { font-family: system-ui, sans-serif; margin: 0; background: #111; color: #eee; padding: 1rem; }
        h1 { margin: 0 0 0.5rem 0; font-size: 1.25rem; }
        .toolbar { display: flex; align-items: center; gap: 1rem; margin-bottom: 1rem; flex-wrap: wrap; }
        a { color: #6af; }
        .video-wrap { background: #000; border-radius: 8px; overflow: hidden; max-width: 100%; }
        .video-wrap img { display: block; width: 100%; height: auto; max-height: 80vh; object-fit: contain; }
        #stats { font-size: 0.875rem; color: #888; }
        .badge { display: inline-block; padding: 0.2rem 0.5rem; border-radius: 4px; margin-right: 0.5rem; }
        .badge.connected { background: #2a2; color: #fff; }
        .badge.disconnected { background: #622; color: #fff; }
    </style>
</head>
<body>
    <h1>Recall video stream (live)</h1>
    <div class="toolbar">
        <span id="status" class="badge disconnected">No stream</span>
        <a href="/api/live/stats" target="_blank">Stats JSON</a>
    </div>
    <div class="video-wrap">
        <img id="stream" src="" alt="Live stream" />
    </div>
    <pre id="stats">Connecting...</pre>
    <script>
        const streamUrl = """ + json.dumps(stream_url) + """;
        const statsUrl = """ + json.dumps(stats_url) + """;
        const img = document.getElementById("stream");
        const statusEl = document.getElementById("status");
        const statsEl = document.getElementById("stats");
        img.src = streamUrl;
        img.onload = () => { statusEl.textContent = "Stream active"; statusEl.className = "badge connected"; };
        img.onerror = () => { statusEl.textContent = "No frames yet"; statusEl.className = "badge disconnected"; };
        async function refreshStats() {
            try {
                const r = await fetch(statsUrl);
                const j = await r.json();
                statsEl.textContent = JSON.stringify(j, null, 2);
                if (j.connected) statusEl.textContent = "Connected • " + (j.last_event_type || "—");
                statusEl.className = "badge " + (j.connected ? "connected" : "disconnected");
            } catch (e) { statsEl.textContent = "Stats: " + e.message; }
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


async def _gemini_live_bridge() -> None:
    """Consume frames from _frame_queue at ~1 FPS and run Gemini Live; broadcast analysis."""
    logger.info("[GEMINI-BRIDGE] Task started.")
    try:
        from app.gemini_live_client import GeminiLiveClient
    except ImportError as e:
        logger.warning("[GEMINI-BRIDGE] Skipped (import error): %s", e)
        return
    if not settings.GEMINI_API_KEY:
        logger.warning("[GEMINI-BRIDGE] Skipped: GEMINI_API_KEY not set. Set it in .env to enable Gemini Live.")
        return

    async def frame_generator():
        while True:
            try:
                frame = await asyncio.wait_for(_frame_queue.get(), timeout=30.0)
                if frame is None:
                    break
                yield frame
            except asyncio.TimeoutError:
                await asyncio.sleep(0.2)
                continue
            except asyncio.CancelledError:
                break

    async def transcript_generator():
        while True:
            try:
                text = await asyncio.wait_for(_transcript_queue.get(), timeout=0.5)
                if text is None:
                    break
                yield text
            except asyncio.TimeoutError:
                continue
            except asyncio.CancelledError:
                break

    async def on_analysis(msg: dict) -> None:
        await _broadcast_analysis(msg)

    client = GeminiLiveClient()
    logger.info("[GEMINI-BRIDGE] Started; waiting for first video frame from Recall, then connecting to Gemini.")
    try:
        await client.run_live_session(
            frame_iterator=frame_generator(),
            transcript_iterator=transcript_generator(),
            analysis_callback=on_analysis,
        )
    except asyncio.CancelledError:
        pass
    except Exception as e:
        logger.exception("Gemini Live bridge error: %s", e)
        await _broadcast_analysis({"error": str(e), "text": str(e)})


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
    Frames are pushed to the Gemini Live bridge at 1 FPS.
    """
    global _recall_ws, _bridge_task, _stream_stats
    logger.info("Recall WebSocket: connection attempt received")
    try:
        await websocket.accept()
    except Exception as e:
        logger.exception("Recall WebSocket: accept failed: %s", e)
        raise
    _recall_ws = websocket
    _stream_stats["connected"] = True
    _stream_stats["events"] = {}
    logger.info("[LIVE] Recall WebSocket connected; starting Gemini Live bridge.")
    try:
        _bridge_task = asyncio.create_task(_gemini_live_bridge())
    except Exception as e:
        logger.exception("Recall WebSocket: bridge task create failed: %s", e)
    try:
        while True:
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
                    try:
                        _frame_queue.put_nowait(frame)
                    except asyncio.QueueFull:
                        _frame_queue.get_nowait()
                        _frame_queue.put_nowait(frame)
                    # Log so we know frames are reaching the bridge (first + every 50th)
                    n = _stream_stats["events"].get(event, 0)
                    if n == 1 or n % 50 == 0:
                        logger.info("[GEMINI-BRIDGE] Video frame queued (%d bytes, %s #%d)", len(frame), event, n)
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
                inner = data.get("data") if isinstance(data, dict) else data
                text = None
                if isinstance(inner, dict):
                    text = inner.get("text") or inner.get("transcript") or inner.get("utterance")
                    if text is None and inner.get("words"):
                        text = " ".join(w.get("text", "") for w in inner["words"])
                elif isinstance(inner, str):
                    text = inner
                if text:
                    try:
                        _transcript_queue.put_nowait(text)
                    except asyncio.QueueFull:
                        _transcript_queue.get_nowait()
                        _transcript_queue.put_nowait(text)
    except WebSocketDisconnect:
        logger.info("Recall WebSocket disconnected")
    except Exception as e:
        logger.exception("Recall WebSocket error: %s", e)
    finally:
        _recall_ws = None
        _stream_stats["connected"] = False
        if _bridge_task:
            _bridge_task.cancel()
            try:
                await _bridge_task
            except asyncio.CancelledError:
                pass
            _bridge_task = None
        _frame_queue.put_nowait(None)
        _transcript_queue.put_nowait(None)


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
