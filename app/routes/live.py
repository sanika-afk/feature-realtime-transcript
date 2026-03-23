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
import os
from typing import Optional, Set, Any, Dict, List
from collections import deque

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, HTTPException, status
from fastapi.responses import StreamingResponse, HTMLResponse
from fastapi.requests import Request

from app.config import settings
from app.models import CreateBotRequest, BotResponse
from app.recall_client import RecallAIClient
from app.routes.bots import parse_meeting_url

# OpenAI client for vision+text analysis
from app.speaker_detector import get_speaker_detector
from app.audio_processor import AudioBuffer
from app.compliance_engine import ComplianceEngine


from app.storage import MEETINGS
from app.summary import generate_summaries

async def process_transcript(meeting_id: str, grouped_data):
    summaries = await generate_summaries(grouped_data)

    MEETINGS[meeting_id] = {
        "status": "completed",
        "summary": summaries
    }


try:
    from app.openai_client import OpenAIClient
except Exception:
    OpenAIClient = None

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
if not logger.handlers:
    _h = logging.StreamHandler()
    _h.setFormatter(logging.Formatter("%(levelname)s: %(message)s"))
    logger.addHandler(_h)

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
_last_partial_text: str = ""
_last_partial_time: float = 0
_last_partial_speaker: Optional[str] = None
_last_partial_metadata: Optional[dict] = None

# Latest video frame from Recall (for MJPEG / HTML viewer)
_latest_frame: Optional[bytes] = None
_latest_frame_mime: str = "image/png"  # Recall sends PNG

# Compliance analysis state
_recent_frames: deque = deque(maxlen=50)   # Buffer of (timestamp, bytes) - ~5s at 10fps
_transcript_buffer: List[str] = []         # Buffer for partial transcript snippets
_transcript_history: List[Dict[str, Any]] = []  # Full history for scrolling panel
_latest_analysis: Optional[Dict[str, Any]] = None
_speaker_detector = get_speaker_detector()  # Initialize speaker detector with buffers
_last_transcript_id: Optional[str] = None

# Initialize OpenAI client if available
_openai_client = None
if OpenAIClient is not None:
    try:
        _openai_client = OpenAIClient()
        logger.info("OpenAI client initialized")
    except Exception as e:
        logger.warning("OpenAI client not initialized: %s", e)

# Compliance analysis state (initialized after dependencies)
_audio_buffer = AudioBuffer(max_seconds= settings.AUDIO_BUFFER_SECONDS if hasattr(settings, "AUDIO_BUFFER_SECONDS") else 120)
_compliance_engine = None


async def _broadcast_analysis(data: dict) -> None:
    """Send analysis JSON to all subscribed clients."""
    if not _analysis_subscribers:
        logger.debug("[BROADCAST] No subscribers, skipping broadcast")
        return
    msg = json.dumps(data)
    dead = set()
    success_count = 0
    for ws in _analysis_subscribers:
        try:
            await ws.send_text(msg)
            success_count += 1
        except Exception as e:
            logger.warning("[BROADCAST] Failed to send to subscriber: %s", e)
            dead.add(ws)
    for ws in dead:
        _analysis_subscribers.discard(ws)
    
    event_type = data.get("event", "unknown")
    logger.debug("[BROADCAST] Sent '%s' to %d/%d subscribers", event_type, success_count, len(_analysis_subscribers))

_compliance_engine = ComplianceEngine(_openai_client, _audio_buffer, _broadcast_analysis)


def _select_best_frame(target_time: float) -> Optional[bytes]:
    """
    Select the best frame from the buffer closest to the target_time.
    Prefers frames captured just before or at the target_time.
    """
    if not _recent_frames:
        return None
    
    best_frame = None
    min_diff = float('inf')
    
    # Frames are (timestamp, bytes)
    for ts, frame in _recent_frames:
        diff = abs(target_time - ts)
        if diff < min_diff:
            min_diff = diff
            best_frame = frame
            
    return best_frame


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
    <title>Live Meeting Analysis - Medical Consultation</title>
    <style>
        * { box-sizing: border-box; }
        body { 
            font-family: 'Inter', system-ui, sans-serif; 
            margin: 0; 
            background: #0a0a0c; 
            color: #f0f0f5; 
            padding: 2rem; 
            display: grid; 
            grid-template-columns: 350px 1fr 1fr; 
            gap: 2rem; 
            height: 100vh; 
        }
        .left-panel { 
            background: #16161d; 
            border-radius: 12px; 
            padding: 1.5rem; 
            display: flex; 
            flex-direction: column; 
            gap: 1.5rem; 
            overflow-y: auto; 
            border: 1px solid #2d2d3d; 
            max-height: 100vh;
        }
        .center-column {
            display: flex;
            flex-direction: column;
            gap: 1rem;
            overflow: hidden;
        }
        .right-panel {
            display: flex;
            flex-direction: column;
            gap: 1rem;
            overflow: hidden;
        }
        h1 { 
            margin: 0; 
            font-size: 1.5rem; 
            background: linear-gradient(90deg, #60a5fa, #a78bfa); 
            -webkit-background-clip: text; 
            -webkit-text-fill-color: transparent; 
            grid-column: 1 / -1;
        }
        .video-wrap { 
            background: #000; 
            border-radius: 12px; 
            overflow: hidden; 
            border: 1px solid #2d2d3d; 
            flex-grow: 1; 
            display: flex; 
            align-items: center; 
            justify-content: center; 
            position: relative; 
        }
        .video-wrap img { 
            width: 100%; 
            height: 100%; 
            object-fit: contain; 
        }
        .overlay { 
            position: absolute; 
            top: 1rem; 
            right: 1rem; 
        }
        .badge { 
            padding: 0.4rem 0.8rem; 
            border-radius: 20px; 
            font-weight: 600; 
            font-size: 0.8rem; 
            text-transform: uppercase; 
            letter-spacing: 0.05em; 
        }
        .badge.connected { 
            background: rgba(34, 197, 94, 0.2); 
            color: #4ade80; 
            border: 1px solid #22c55e; 
        }
        .badge.disconnected { 
            background: rgba(239, 68, 68, 0.2); 
            color: #f87171; 
            border: 1px solid #ef4444; 
        }
        .analysis-card { 
            background: #1f1f29; 
            border-radius: 10px; 
            padding: 1.5rem; 
            border-left: 4px solid #60a5fa; 
            display: flex;
            flex-direction: column;
            gap: 1rem;
        }
        .analysis-card h3 { 
            margin: 0; 
            font-size: 0.9rem; 
            color: #94a3b8; 
            text-transform: uppercase; 
            letter-spacing: 0.05em;
        }
        .risk-badge {
            padding: 0.25rem 0.6rem;
            border-radius: 4px;
            font-size: 0.75rem;
            font-weight: 700;
            text-transform: uppercase;
        }
        .risk-low { background: #064e3b; color: #6ee7b7; }
        .risk-medium { background: #78350f; color: #fcd34d; }
        .risk-high { background: #7f1d1d; color: #fca5a5; }
        .risk-badge.risk-critical { background: #fee2e2; color: #991b1b; border: 1px solid #f87171; }
        .risk-badge.risk-major { background: #ffedd5; color: #9a3412; border: 1px solid #fb923c; }
        .risk-badge.risk-minor { background: #fef9c3; color: #854d0e; border: 1px solid #facc15; }
        .risk-badge.risk-none { background: #dcfce7; color: #166534; border: 1px solid #4ade80; }

        .interpretation-card {
            background: #1e1b4b; /* Deep Indigo */
            border-radius: 12px;
            padding: 1.25rem;
            border-left: 6px solid #4f46e5;
            box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
            animation: slideIn 0.3s ease-out;
            margin-bottom: 1rem;
        }
        .interpretation-card.severity-critical { border-left-color: #ef4444; background: #450a0a; }
        .interpretation-card.severity-major { border-left-color: #f97316; background: #431407; }
        .interpretation-card.severity-minor { border-left-color: #facc15; background: #3f2c06; }
        .interpretation-card.severity-none { border-left-color: #22c55e; background: #064e3b; }

        @keyframes slideIn {
            from { opacity: 0; transform: translateY(10px); }
            to { opacity: 1; transform: translateY(0); }
        }

        .stat-grid {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 1rem;
        }
        .stat-item {
            background: #16161d;
            padding: 0.75rem;
            border-radius: 8px;
            text-align: center;
            border: 1px solid #2d2d3d;
        }
        .stat-value {
            font-size: 1.25rem;
            font-weight: 700;
            color: #fff;
        }
        .stat-label {
            font-size: 0.7rem;
            color: #94a3b8;
            text-transform: uppercase;
            margin-top: 0.25rem;
        }
        @media (max-width: 1400px) { 
            body { 
                grid-template-columns: 1fr; 
                height: auto; 
            } 
            .left-panel { 
                max-height: 400px; 
            }
        }
    </style>
</head>
<body>
    <div class="left-panel">
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.5rem;">
            <h1 style="margin: 0; font-size: 1.2rem;">Meeting Bot</h1>
            <span id="status" class="badge disconnected">Disconnected</span>
        </div>
        
            <!-- Transcript History Panel -->
            <div class="transcript-panel" style="flex-grow: 1; display: flex; flex-direction: column;">
                <h3 style="color: #94a3b8; font-size: 0.8rem; text-transform: uppercase; margin-bottom: 0.5rem;">📋 Transcript History</h3>
                <div id="transcript-history" style="flex-grow: 1; overflow-y: auto; background: #000; padding: 0.75rem; border-radius: 8px; font-size: 0.85rem; border: 1px solid #2d2d3d;">
                    <div style="color: #4b5563; font-style: italic;">Waiting for transcript data...</div>
                </div>
            </div>
    </div>

    <div class="center-column">
        <div style="display: flex; justify-content: space-between; align-items: center;">
            <h1 style="margin: 0; grid-column: auto;">Live Meeting Analysis</h1>
        </div>
        
        <!-- Video Stream -->
        <div class="video-wrap">
            <img id="stream" src="" alt="Meeting Stream" />
            <div class="overlay">
                <span id="video-status" class="badge connected">Video Active</span>
            </div>
        </div>
    </div>

    <div class="right-panel">
        <!-- Compliance Analysis Card -->
        <div class="analysis-card" id="analysis-card">
            <div style="display: flex; justify-content: space-between; align-items: flex-start;">
                <h3>✅ AI Audit Results</h3>
                <span id="risk-level" class="risk-badge" style="display: none;">Low</span>
            </div>
            
            <div id="analysis-summary" style="font-size: 1rem; color: #e2e8f0; line-height: 1.4;">
                Waiting for final sentence analysis...
            </div>
            
            <div class="stat-grid">
                <div class="stat-item">
                    <div class="stat-value" id="confidence-score">--</div>
                    <div class="stat-label">AI Confidence</div>
                </div>
                <div class="stat-item">
                    <div class="stat-value" id="person-count">--</div>
                    <div class="stat-label">Participants</div>
                </div>
            </div>

            <div id="analysis-timestamp" style="font-size: 0.7rem; color: #4b5563; text-align: right; margin-top: auto;">
                No analysis yet
            </div>
        </div>
        
        <!-- Stats Display -->
        <div style="margin-top: auto;">
            <h3 style="font-size: 0.8rem; color: #64748b; margin: 0 0 0.5rem 0;">Raw Stream Stats</h3>
            <pre id="stats" style="background: #000; padding: 1rem; border-radius: 8px; font-size: 0.75rem; color: #64748b; overflow-x: auto; margin: 0; border: 1px solid #2d2d3d;">Connecting to stats API...</pre>
        </div>
    </div>

    <script>
        const streamUrl = """ + json.dumps(stream_url) + """;
        const statsUrl = """ + json.dumps(stats_url) + """;
        const img = document.getElementById("stream");
        const statusEl = document.getElementById("status");
        const statsEl = document.getElementById("stats");
        
        img.src = streamUrl;
        img.onload = () => { 
            statusEl.textContent = "Stream Active"; 
            statusEl.className = "badge connected"; 
            document.getElementById("video-status").textContent = "Video Active";
        };
        img.onerror = () => { 
            statusEl.textContent = "No Frames"; 
            statusEl.className = "badge disconnected";
            document.getElementById("video-status").textContent = "No Video";
        };

        // WebSocket Connection Logic
        let ws;
        let reconnectTimer;
        // Get the Public WS URL from environment, fallback to null
        const publicWsUrlRaw = """ + json.dumps(os.environ.get("PUBLIC_WS_URL", "")) + """;
        const publicWsUrl = publicWsUrlRaw ? publicWsUrlRaw.replace(/\/$/, "") : "";
        
        let wsUrl;
        if (publicWsUrl) {
            // If public URL is provided (e.g. Tunnel), use it.
            // Ensure it has the correct path
            if (publicWsUrl.includes("/Analysis")) {
                 wsUrl = publicWsUrl;
            } else {
                 wsUrl = `${publicWsUrl}/api/live/ws/analysis`;
            }
        } else {
            // Fallback to browser's current location
            const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
            wsUrl = `${protocol}//${window.location.host}/api/live/ws/analysis`;
        }

        function updateConnectionStatus(state) {
            const el = document.getElementById("stats");
            if (state === "OPEN") {
                el.style.borderColor = "#22c55e";
                el.textContent = "● Live Analysis Connected";
            } else if (state === "CONNECTING") {
                el.style.borderColor = "#eab308";
                el.textContent = "○ Connecting...";
            } else {
                el.style.borderColor = "#ef4444";
                el.textContent = "× Disconnected (Retrying...)";
            }
        }

        function connectWebSocket() {
            if (ws && (ws.readyState === WebSocket.OPEN || ws.readyState === WebSocket.CONNECTING)) return;
            
            console.log("Connecting to WebSocket:", wsUrl);
            updateConnectionStatus("CONNECTING");
            
            ws = new WebSocket(wsUrl);
            
            ws.onopen = () => {
                console.log("Real-time analysis connected");
                updateConnectionStatus("OPEN");
                if (reconnectTimer) clearInterval(reconnectTimer);
            };
            
            ws.onclose = () => {
                console.log("Real-time analysis disconnected");
                updateConnectionStatus("CLOSED");
                // Try to reconnect in 3 seconds
                if (reconnectTimer) clearTimeout(reconnectTimer);
                reconnectTimer = setTimeout(connectWebSocket, 3000);
            };
            
            ws.onerror = (err) => {
                console.error("WebSocket error:", err);
                ws.close();
            };

            ws.onmessage = (event) => {
                try {
                    const data = JSON.parse(event.data);
                    updateAnalysisUI(data);
                } catch (e) {
                    console.error("Error parsing WS message:", e);
                }
            };
        }

        // Start connection
        connectWebSocket();

        function showApiWarning(message) {
            let warningEl = document.getElementById("api-quota-warning");
            if (!warningEl) {
                warningEl = document.createElement("div");
                warningEl.id = "api-quota-warning";
                warningEl.style.cssText = "background: #7f1d1d; color: #fca5a5; padding: 0.75rem; border-radius: 8px; margin-bottom: 1rem; border: 1px solid #ef4444; font-size: 0.85rem; font-weight: 600;";
                document.querySelector(".left-panel").prepend(warningEl);
            }
            warningEl.textContent = "⚠️ " + message;
        }

        function updateAnalysisUI(data) {
            console.log("[WS] Received event:", data.event, data);
            
            // Case 0: History Initialization
            if (data.event === "history_init") {
                const initData = data.data;
                console.log("[WS] History init received:", initData.total_entries || initData.history?.length || 0, "entries");
                
                // Clear the transcript history panel first
                const histEl = document.getElementById("transcript-history");
                histEl.innerHTML = "";
                
                // Load history entries
                if (initData.history && initData.history.length > 0) {
                    console.log("[WS] Rendering", initData.history.length, "history entries");
                    initData.history.forEach((item, index) => {
                        console.log(`[WS] History entry ${index}:`, item);
                        updateAnalysisUI({ event: "transcript_final", data: item });
                    });
                } else {
                    console.log("[WS] No history entries to render");
                    histEl.innerHTML = '<div style="color: #4b5563; font-style: italic;">No transcript history yet...</div>';
                }
                
                // Update latest analysis if available
                if (initData.latest_analysis) {
                    console.log("[WS] Updating latest analysis from history");
                    updateAnalysisUI({ event: "analysis_update", data: initData.latest_analysis });
                }
                return;
            }

            // Case 1: Analysis Update (Audit Results)
            if (data.event === "analysis_update") {
                const results = data.data.analysis;
                
                if (results.error_type === "QUOTA_EXCEEDED") {
                    showApiWarning("OpenAI Quota Exceeded. Please check your billing at platform.openai.com.");
                }

                document.getElementById("analysis-summary").textContent = results.summary || "No summary.";
                
                const confidence = results.confidence || 0;
                document.getElementById("confidence-score").textContent = confidence + "%";
                
                const risk = (results.risk_level || "Low").toLowerCase();
                const riskEl = document.getElementById("risk-level");
                riskEl.textContent = results.risk_level;
                riskEl.style.display = "inline-block";
                riskEl.className = "risk-badge risk-" + risk;
                
                document.getElementById("analysis-timestamp").textContent = "Last analysis: " + (data.data.timestamp || "Just now");
                
                if (data.data.raw_details && data.data.raw_details.person_count !== undefined) {
                    document.getElementById("person-count").textContent = data.data.raw_details.person_count;
                }
            }
            
            // Case 2: Interpretation Accuracy Event
            if (data.event === "interpretation_accuracy") {
                const payload = data.data;

                if (payload.issue_type === "QUOTA_EXCEEDED") {
                    showApiWarning("OpenAI Quota Exceeded. Interpretation checks are paused.");
                }

                const histEl = document.getElementById("transcript-history");
                
                const entry = document.createElement("div");
                entry.className = `interpretation-card severity-${(payload.severity || "None").toLowerCase()}`;
                entry.style.marginTop = "0.75rem";
                
                // Construct the card
                entry.innerHTML = `
                    <div style="display: flex; justify-content: space-between; align-items: start; margin-bottom: 0.5rem;">
                        <span class="badge" style="background: #ef4444; color: white;">ACCURACY CHECK</span>
                        <span style="font-size: 0.75rem; color: #94a3b8;">${payload.timestamp}</span>
                    </div>
                    <div style="font-size: 0.85rem; color: #e2e8f0; margin-bottom: 0.5rem;">
                        <strong>🩺 Doctor:</strong> "${payload.doctor_text}"
                    </div>
                    <div style="font-size: 0.85rem; color: #e2e8f0; margin-bottom: 0.5rem;">
                        <strong>🗣️ Interpreter:</strong> "${payload.interpreter_text}"
                    </div>
                    <div style="margin-top: 0.5rem; padding-top: 0.5rem; border-top: 1px solid #ffffff10;">
                        <span class="risk-badge risk-${(payload.severity || "None").toLowerCase()}">${payload.severity}</span>
                        <span style="font-size: 0.85rem; color: #facc15; margin-left: 0.5rem;">Issue: ${payload.issue_type}</span>
                    </div>
                    <div style="font-size: 0.8rem; color: #94a3b8; margin-top: 0.5rem; font-style: italic;">
                        Notes: ${payload.notes}
                    </div>
                `;
                
                histEl.prepend(entry);
                return;
            }


            // Case 3: Finalized Transcript
            if (data.event === "transcript_final") {
                const payload = data.data;
                const histEl = document.getElementById("transcript-history");
                
                // Remove empty state if present
                const emptyState = histEl.querySelector('[style*="italic"]');
                if (emptyState && (emptyState.textContent.includes("Waiting") || emptyState.textContent.includes("No transcript"))) {
                    emptyState.remove();
                }
                
                const entry = document.createElement("div");
                const timeStr = payload.timestamp || new Date().toLocaleTimeString();
                const speaker = payload.speaker_role || "Unknown";
                const speakerColor = speaker === "Doctor" ? "#3b82f6" : (speaker === "Patient" ? "#10b981" : "#8b5cf6");
                
                entry.innerHTML = `
                    <div style="display: flex; gap: 8px; align-items: flex-start;">
                        <span style="color: #4b5563; font-size: 0.7rem; white-space: nowrap;">[${timeStr}]</span>
                        <div>
                            <span style="color: ${speakerColor}; font-weight: 600; font-size: 0.75rem; text-transform: uppercase;">${speaker}:</span>
                            <span style="color: #e2e8f0;">${payload.text}</span>
                        </div>
                    </div>
                `;
                
                histEl.appendChild(entry);
                histEl.scrollTop = histEl.scrollHeight;
                console.log("[WS] Added transcript entry:", speaker, payload.text.substring(0, 50));
                return;
            }

            // Case 4: AI Role Correction
            if (data.event === "ai_role_correction") {
                const payload = data.data;
                const histEl = document.getElementById("transcript-history");
                
                // Find all entry divs
                const entries = histEl.querySelectorAll("div[style*='align-items: flex-start']");
                if (entries.length > 0) {
                    // Start from the end and find the one matching this text
                    for (let i = entries.length - 1; i >= 0; i--) {
                        const entry = entries[i];
                        const textSpan = entry.querySelector("span[style*='#e2e8f0']");
                        if (textSpan && textSpan.textContent === payload.text) {
                            const labelSpan = entry.querySelector("span[style*='font-weight: 600']");
                            if (labelSpan) {
                                const newRole = payload.ai_role;
                                const newColor = newRole === "Doctor" ? "#3b82f6" : (newRole === "Patient" ? "#10b981" : "#facc15");
                                labelSpan.textContent = newRole.toUpperCase() + " (AI):";
                                labelSpan.style.color = newColor;
                                console.log("[WS] Corrected speaker role to:", newRole);
                            }
                            break;
                        }
                    }
                }
                return;
            }
        }

        async function refreshStats() {
            try {
                const r = await fetch(statsUrl);
                const j = await r.json();
                
                // Update raw stats display
                statsEl.textContent = JSON.stringify({
                    events: j.events, 
                    last_event: j.last_event_type,
                    connected: j.connected
                }, null, 2);
                
                // Update Badge
                if (j.connected) {
                    statusEl.textContent = "Connected";
                    statusEl.className = "badge connected";
                } else {
                    statusEl.textContent = "Disconnected";
                    statusEl.className = "badge disconnected";
                }
                
                // Update analysis UI fallback (polling)
                if (j.latest_analysis) {
                    // Mapping polling data to same structure as WS
                    updateAnalysisUI({
                        event: "analysis_update",
                        data: j.latest_analysis
                    });
                }

            } catch (e) { 
                statsEl.textContent = "Error: " + e.message; 
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
    base = settings.PUBLIC_WS_URL.strip().rstrip("/")
    websocket_url = f"{base}/api/live/ws/recall"
    logger.info(f"[BOT-CREATE] Creating bot with WebSocket URL: {websocket_url}")
    try:
        bot_data = await recall_client.create_bot_with_websocket(
            meeting_url=str(request.meeting_url),
            websocket_url=websocket_url,
            video_layout=request.video_layout,
            auto_leave=request.auto_leave,
            bot_name=request.bot_name,
            events=request.events,
            language=request.transcription_language
        )
        logger.info(f"[BOT-CREATE] Bot created with ID: {bot_data.get('id')}, Status: {bot_data.get('status')}")
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
        logger.error(f"[BOT-CREATE] Failed to create bot: {e}")
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


@router.get("/connection-status")
async def connection_status():
    """Debug endpoint to check WebSocket connection status."""
    return {
        "ws_connected": _stream_stats.get("connected", False),
        "public_ws_url": settings.PUBLIC_WS_URL,
        "expected_endpoint": f"{settings.PUBLIC_WS_URL}/api/live/ws/recall" if settings.PUBLIC_WS_URL else "NOT SET",
        "events_received": dict(_stream_stats.get("events", {})),
        "last_event_type": _stream_stats.get("last_event_type"),
        "last_event_at": _stream_stats.get("last_event_at"),
    }


@router.get("/transcript-debug")
async def transcript_debug():
    """Debug endpoint to inspect transcript history and WebSocket state."""
    return {
        "transcript_history_count": len(_transcript_history),
        "transcript_history_sample": _transcript_history[-5:] if _transcript_history else [],
        "latest_analysis": _latest_analysis,
        "analysis_subscribers_count": len(_analysis_subscribers),
        "recall_ws_connected": _recall_ws is not None,
        "stream_stats": _stream_stats,
        "last_partial_text": _last_partial_text[:100] if _last_partial_text else None,
        "last_partial_time": _last_partial_time,
        "last_partial_speaker": _last_partial_speaker
    }



@router.get("/buffers")
async def get_speaker_buffers() -> Dict[str, Any]:
    """Get current speaker buffers and statistics."""
    return {
        "buffers": _speaker_detector.get_all_buffers(),
        "stats": _speaker_detector.get_buffer_stats(),
        "speaker_roles": _speaker_detector.get_speaker_summary(),
        "transcript_history": _transcript_history[-50:]  # Last 50 entries
    }


@router.post("/buffers/clear")
async def clear_speaker_buffers() -> Dict[str, str]:
    """Clear all speaker buffers."""
    _speaker_detector.clear_buffers()
    _transcript_history.clear()
    logger.info("[BUFFERS] Cleared all speaker buffers")
    return {"status": "cleared"}





@router.get("/transcript-summary")
async def get_transcript_summary() -> Dict[str, Any]:
    """Get formatted transcript summary with speaker identification (Doctor, Patient, Interpreter)."""
    summary = {
        "total_entries": len(_transcript_history),
        "doctor_segments": [],
        "interpreter_segments": [],
        "patient_segments": [],
        "raw_entries": _transcript_history
    }
    
    for entry in _transcript_history:
        role = entry.get("speaker_role", "Unknown")
        text = entry.get("text", "")
        timestamp = entry.get("timestamp", 0)
        
        segment = {
            "timestamp": timestamp,
            "speaker_id": entry.get("speaker_id"),
            "text": text
        }
        
        if "Doctor" in role or "doctor" in role.lower():
            summary["doctor_segments"].append(segment)
        elif "Interpreter" in role or "interpreter" in role.lower():
            summary["interpreter_segments"].append(segment)
        elif "Patient" in role or "patient" in role.lower():
            summary["patient_segments"].append(segment)
    
    return summary



MEETINGS = {
    "meeting_123": {
        "status": "completed",
        "summary": {
            "John": "...",
            "Priya": "..."
        }
    }
}