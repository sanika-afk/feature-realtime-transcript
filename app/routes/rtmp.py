from fastapi import APIRouter, Request, Response, HTTPException
from fastapi.responses import StreamingResponse
import httpx
import logging
from typing import List, Dict, Any
from app.config import settings
import xml.etree.ElementTree as ET

router = APIRouter(prefix="/rtmp", tags=["rtmp"])
logger = logging.getLogger(__name__)


@router.post("/publish")
async def rtmp_publish(request: Request):
    """
    RTMP publish endpoint.
    
    This endpoint receives RTMP streams from Recall.ai bots.
    In production, you would use an RTMP server like nginx-rtmp or SRS.
    This is a placeholder for the RTMP handling logic.
    """
    # Note: FastAPI cannot directly handle RTMP protocol
    # You need an RTMP server (nginx-rtmp, SRS, or similar) to receive the stream
    # This endpoint is for documentation purposes
    
    logger.info("RTMP publish request received")
    return {"message": "RTMP stream received", "note": "Use nginx-rtmp or SRS for actual RTMP handling"}


@router.get("/streams", response_model=List[Dict[str, Any]])
async def list_active_streams():
    """
    List all active streams from nginx-rtmp server.
    
    Returns list of active streams with their stream keys and URLs.
    """
    try:
        # nginx-rtmp stats endpoint (XML format)
        wsl_ip = "172.31.88.58"  # WSL IP address
        stats_url = f"http://{wsl_ip}:8080/stat"
        
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(stats_url)
            response.raise_for_status()
            
            # Parse XML response
            root = ET.fromstring(response.text)
            streams = []
            
            # Find all applications
            for app in root.findall(".//application"):
                app_name = app.find("name")
                if app_name is None:
                    continue
                
                # Find all streams in this application
                for stream in app.findall(".//stream"):
                    name_elem = stream.find("name")
                    if name_elem is None:
                        continue
                    
                    stream_key = name_elem.text
                    if stream_key:
                        # Get video/audio info
                        video_elem = stream.find("video")
                        audio_elem = stream.find("audio")
                        
                        video_info = {}
                        audio_info = {}
                        
                        if video_elem is not None:
                            video_info = {
                                "width": video_elem.findtext("width", ""),
                                "height": video_elem.findtext("height", ""),
                                "fps": video_elem.findtext("fps", ""),
                                "codec": video_elem.findtext("codec", "")
                            }
                        
                        if audio_elem is not None:
                            audio_info = {
                                "codec": audio_elem.findtext("codec", ""),
                                "sample_rate": audio_elem.findtext("sample_rate", ""),
                                "channels": audio_elem.findtext("channels", "")
                            }
                        
                        streams.append({
                            "stream_key": stream_key,
                            "app": app_name.text or "live",
                            "hls_url": f"http://{wsl_ip}:8080/hls/{stream_key}.m3u8",
                            "rtmp_url": f"rtmp://{wsl_ip}:1935/{app_name.text or 'live'}/{stream_key}",
                            "clients": len(stream.findall(".//client")),
                            "video": video_info,
                            "audio": audio_info
                        })
            
            return streams
    except httpx.RequestError as e:
        logger.error(f"Failed to connect to nginx-rtmp: {e}")
        raise HTTPException(
            status_code=503,
            detail="nginx-rtmp server is not accessible. Make sure nginx-rtmp is running on port 8080."
        )
    except ET.ParseError as e:
        logger.error(f"Failed to parse nginx-rtmp stats XML: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to parse nginx-rtmp stats: {str(e)}"
        )
    except Exception as e:
        logger.error(f"Error fetching streams: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch streams: {str(e)}"
        )


@router.get("/stream/{stream_key}")
async def get_stream_info(stream_key: str):
    """
    Get information about a specific stream.
    
    Returns stream details and playback URLs.
    """
    wsl_ip = "172.31.88.58"  # WSL IP address
    return {
        "stream_key": stream_key,
        "hls_url": f"http://{wsl_ip}:8080/hls/{stream_key}.m3u8",
        "rtmp_url": f"rtmp://{wsl_ip}:1935/live/{stream_key}",
        "viewer_url": f"http://localhost:8000/viewer?stream={stream_key}",
        "note": "Stream will be available once the bot starts streaming"
    }
