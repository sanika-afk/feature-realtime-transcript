"""
Real-time HIPAA Compliance Analysis Routes
Analyzes medical consultation videos for HIPAA compliance using AI.

IMPORTANT: All analysis is performed by AI models (Video Intelligence API and Gemini).
This backend:
1. Extracts frames from RTMP stream
2. Sends frames to both Video Intelligence API and Gemini for comparison
3. Analyzes audio for disturbances
4. Forwards AI analysis results to clients via WebSocket

All compliance checks, person detection, and QA metrics are determined by AI.
"""
from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import StreamingResponse, JSONResponse
from typing import Dict, Any, Optional, Iterator
import asyncio
import logging
import json
from app.config import settings
from app.rtmp_capture import RTMPStreamCapture
from app.video_intelligence_client import VideoIntelligenceStreamingClient
from app.gemini_client import GeminiClient
from app.hipaa_analyzer import HIPAAComplianceAnalyzer
from google.cloud.videointelligence_v1 import Feature

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/analysis", tags=["analysis"])

# Store active analysis sessions
active_sessions: Dict[str, Dict[str, Any]] = {}


@router.post("/start/{stream_key}")
async def start_analysis(
    stream_key: str,
    features: Optional[str] = None,
    fps: int = 1
):
    """
    Start real-time HIPAA compliance analysis of a medical consultation stream.
    
    Analyzes frames using both Video Intelligence API and Gemini for comparison.
    All analysis logic is handled by AI models.
    
    Args:
        stream_key: Stream key to analyze
        features: Comma-separated list (kept for compatibility)
        fps: Frames per second to extract and analyze (default: 1)
    
    Returns:
        Analysis session information
    """
    try:
        # Get RTMP URL
        wsl_ip = "172.31.88.58"
        rtmp_url = f"rtmp://{wsl_ip}:1935/live/{stream_key}"
        
        # Initialize capture (will extract frames)
        capture = RTMPStreamCapture(rtmp_url, fps=fps)
        
        # Initialize Video Intelligence client (supports both API key and service account)
        vi_client = VideoIntelligenceStreamingClient(
            credentials_path=settings.GOOGLE_APPLICATION_CREDENTIALS,
            project_id=settings.GOOGLE_CLOUD_PROJECT_ID,
            api_key=settings.GOOGLE_CLOUD_API_KEY
        )
        
        # Initialize Gemini client
        gemini_client = GeminiClient(api_key=settings.GEMINI_API_KEY)
        
        # Initialize HIPAA analyzer
        hipaa_analyzer = HIPAAComplianceAnalyzer(vi_client, gemini_client)
        
        # Store session
        session_id = f"{stream_key}_{asyncio.get_event_loop().time()}"
        active_sessions[session_id] = {
            "stream_key": stream_key,
            "rtmp_url": rtmp_url,
            "capture": capture,
            "vi_client": vi_client,
            "gemini_client": gemini_client,
            "hipaa_analyzer": hipaa_analyzer,
            "fps": fps,
            "status": "starting"
        }
        
        return {
            "session_id": session_id,
            "stream_key": stream_key,
            "rtmp_url": rtmp_url,
            "analysis_type": "HIPAA Compliance & Medical Interpreter QA",
            "apis_used": ["Video Intelligence API", "Gemini"],
            "fps": fps,
            "status": "started",
            "websocket_url": f"/api/analysis/stream/{session_id}"
        }
        
    except Exception as e:
        logger.error(f"Error starting analysis: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to start analysis: {str(e)}"
        )


@router.websocket("/stream/{session_id}")
async def stream_analysis(websocket: WebSocket, session_id: str):
    """
    WebSocket endpoint for real-time analysis results.
    
    Connects to the analysis session and streams results as they come in.
    """
    await websocket.accept()
    
    if session_id not in active_sessions:
        await websocket.close(code=1008, reason="Session not found")
        return
    
    session = active_sessions[session_id]
    capture = session["capture"]
    hipaa_analyzer = session["hipaa_analyzer"]
    
    async def _process_audio_stream(audio_stream):
        """Process audio stream for disturbance detection (placeholder for future implementation)."""
        try:
            async for audio_chunk in audio_stream:
                # TODO: Integrate with Speech-to-Text and analyze for disturbances
                # For now, this is a placeholder
                pass
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"Error processing audio: {e}")
    
    try:
        session["status"] = "running"
        
        # Start analysis task
        async def analyze_stream():
            try:
                # Extract frames from RTMP stream
                frame_stream = capture.capture_frames()
                
                # Also capture audio for disturbance detection
                audio_stream = capture.capture_audio()
                audio_task = asyncio.create_task(_process_audio_stream(audio_stream))
                
                frame_count = 0
                async for frame in frame_stream:
                    frame_count += 1
                    
                    # Analyze frame with both APIs (AI handles all logic)
                    analysis_result = await hipaa_analyzer.analyze_frame_dual(frame)
                    
                    # Send comprehensive analysis results
                    await websocket.send_json({
                        "type": "analysis_result",
                        "frame_number": frame_count,
                        "data": analysis_result,
                        "timestamp": asyncio.get_event_loop().time()
                    })
                    
                    # Check for critical violations
                    compliance_status = analysis_result.get("combined_analysis", {}).get("compliance_status")
                    if compliance_status in ["NON_COMPLIANT", "CRITICAL_VIOLATIONS"]:
                        await websocket.send_json({
                            "type": "compliance_alert",
                            "severity": compliance_status,
                            "details": analysis_result.get("combined_analysis", {}),
                            "timestamp": asyncio.get_event_loop().time()
                        })
                
                # Cancel audio task when done
                audio_task.cancel()
                            
            except Exception as e:
                logger.error(f"Error in analysis stream: {e}")
                await websocket.send_json({
                    "type": "error",
                    "message": str(e)
                })
        
        # Run analysis
        analysis_task = asyncio.create_task(analyze_stream())
        
        # Keep connection alive and handle client messages
        while True:
            try:
                # Wait for client message or analysis completion
                data = await asyncio.wait_for(websocket.receive_text(), timeout=1.0)
                # Handle client messages if needed
                if data == "stop":
                    break
            except asyncio.TimeoutError:
                # Check if analysis is still running
                if session["status"] != "running":
                    break
                continue
            except WebSocketDisconnect:
                break
        
        # Cleanup
        analysis_task.cancel()
        capture.stop()
        session["status"] = "stopped"
        
    except Exception as e:
        logger.error(f"Error in WebSocket stream: {e}")
        await websocket.send_json({
            "type": "error",
            "message": str(e)
        })
    finally:
        await websocket.close()


@router.get("/status/{session_id}")
async def get_analysis_status(session_id: str):
    """Get status of an analysis session."""
    if session_id not in active_sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    
    session = active_sessions[session_id]
    return {
        "session_id": session_id,
        "stream_key": session["stream_key"],
        "status": session["status"],
        "fps": session.get("fps", 1),
        "summary": session.get("hipaa_analyzer").get_summary() if session.get("hipaa_analyzer") and hasattr(session.get("hipaa_analyzer"), "get_summary") else None
    }


@router.post("/stop/{session_id}")
async def stop_analysis(session_id: str):
    """Stop an analysis session."""
    if session_id not in active_sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    
    session = active_sessions[session_id]
    capture = session["capture"]
    capture.stop()
    session["status"] = "stopped"
    
    return {
        "session_id": session_id,
        "status": "stopped"
    }


@router.get("/sessions")
async def list_analysis_sessions():
    """List all active analysis sessions."""
    return {
        "sessions": [
            {
                "session_id": sid,
                "stream_key": session["stream_key"],
                "status": session["status"],
                "features": [f.name for f in session["features"]]
            }
            for sid, session in active_sessions.items()
        ]
    }
