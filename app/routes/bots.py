from fastapi import APIRouter, HTTPException, status
from typing import List
import uuid
import httpx
import logging
from app.models import CreateBotRequest, BotResponse, BotStatusResponse
from app.recall_client import RecallAIClient
from app.config import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/bots", tags=["bots"])
recall_client = RecallAIClient()


def parse_meeting_url(meeting_url_value, meeting_metadata=None):
    """
    Parse meeting_url from Recall.ai response.
    It can be a string or a dict with meeting_id and platform.
    """
    if meeting_metadata is None:
        meeting_metadata = {}
    
    if isinstance(meeting_url_value, dict):
        meeting_id = meeting_url_value.get("meeting_id", "")
        platform = meeting_url_value.get("platform", "")
        
        # Construct URL based on platform
        if meeting_id:
            if platform == "google_meet":
                meeting_url_str = f"https://meet.google.com/{meeting_id}"
            elif platform == "zoom":
                meeting_url_str = f"https://zoom.us/j/{meeting_id}"
            elif platform == "teams":
                meeting_url_str = meeting_id  # Teams URLs are usually full URLs
            else:
                meeting_url_str = meeting_id
        else:
            meeting_url_str = None
        
        # Store original dict in metadata
        meeting_metadata = {**meeting_metadata, "meeting_info": meeting_url_value}
    else:
        meeting_url_str = meeting_url_value
    
    return meeting_url_str, meeting_metadata


@router.post("/", response_model=BotResponse, status_code=status.HTTP_201_CREATED)
async def create_bot(request: CreateBotRequest):
    """
    Create a bot that joins a meeting and streams via RTMP.
    
    The bot will:
    - Join the specified meeting URL
    - Stream video + audio at 720p, 30fps via RTMP
    - Use the configured video layout (speaker view or gallery view)
    """
    try:
        # Generate RTMP URL
        stream_key = request.stream_key or f"{settings.RTMP_STREAM_KEY_PREFIX}-{uuid.uuid4().hex[:8]}"
        
        # Construct RTMP URL
        # Format: rtmp://hostname[:port]/{APPLICATION-NAME}/{STREAM-KEY}
        if settings.PUBLIC_RTMP_URL:
            # Use public URL if configured (for production or ngrok)
            # Remove trailing slashes and /live if present to avoid duplication
            public_url = settings.PUBLIC_RTMP_URL.rstrip('/')
            if public_url.endswith('/live'):
                public_url = public_url[:-5]  # Remove trailing /live
            rtmp_url = f"{public_url}/{settings.RTMP_APPLICATION}/{stream_key}"
        else:
            # Local development URL
            rtmp_url = f"rtmp://{settings.RTMP_HOST}:{settings.RTMP_PORT}/{settings.RTMP_APPLICATION}/{stream_key}"
        
        # Create bot via Recall.ai
        bot_data = await recall_client.create_bot(
            meeting_url=str(request.meeting_url),
            rtmp_url=rtmp_url,
            video_layout=request.video_layout,
            auto_leave=request.auto_leave,
            bot_name=request.bot_name
        )
        
        # Handle meeting_url - it can be a string or a dict
        meeting_url_str, meeting_metadata = parse_meeting_url(
            bot_data.get("meeting_url"),
            bot_data.get("meeting_metadata") or {}
        )
        
        return BotResponse(
            id=bot_data.get("id"),
            status=bot_data.get("status", "unknown"),
            bot_name=bot_data.get("bot_name"),
            stream_key=stream_key,
            meeting_url=meeting_url_str,
            meeting_metadata=meeting_metadata,
            created_at=bot_data.get("created_at"),
            error_message=bot_data.get("error_message")
        )
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create bot: {str(e)}"
        )


@router.get("/{bot_id}", response_model=BotStatusResponse)
async def get_bot(bot_id: str):
    """
    Get detailed status of a bot.
    
    Returns bot information from Recall.ai API including status, meeting details, and recording info.
    See: https://docs.recall.ai/reference/bot_retrieve
    """
    try:
        bot_data = await recall_client.get_bot(bot_id)
        
        # Log the full response for debugging (remove in production)
        logger.debug(f"Recall.ai bot response: {bot_data}")
        
        # Handle meeting_url - it can be a string or a dict
        meeting_url_str, meeting_metadata = parse_meeting_url(
            bot_data.get("meeting_url"),
            bot_data.get("meeting_metadata") or {}
        )
        
        # Get status - Recall.ai uses various status values
        status = bot_data.get("status", "unknown")
        
        return BotStatusResponse(
            id=bot_data.get("id"),
            status=status,
            bot_name=bot_data.get("bot_name"),
            meeting_url=meeting_url_str,
            meeting_metadata=meeting_metadata,
            recording=bot_data.get("recording"),
            created_at=bot_data.get("created_at"),
            error_message=bot_data.get("error_message")
        )
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 404:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Bot not found"
            )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get bot: {str(e)}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get bot: {str(e)}"
        )


@router.get("/", response_model=List[BotResponse])
async def list_bots(limit: int = 10, offset: int = 0):
    """List all bots."""
    try:
        response = await recall_client.list_bots(limit=limit, offset=offset)
        bots = response.get("results", [])
        result = []
        for bot in bots:
            # Handle meeting_url - it can be a string or a dict
            meeting_url_str, meeting_metadata = parse_meeting_url(
                bot.get("meeting_url"),
                bot.get("meeting_metadata") or {}
            )
            
            result.append(BotResponse(
                id=bot.get("id"),
                status=bot.get("status", "unknown"),
                bot_name=bot.get("bot_name"),
                meeting_url=meeting_url_str,
                meeting_metadata=meeting_metadata,
                created_at=bot.get("created_at"),
                error_message=bot.get("error_message")
            ))
        return result
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list bots: {str(e)}"
        )


@router.delete("/{bot_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_bot(bot_id: str):
    """Stop and delete a bot."""
    try:
        await recall_client.delete_bot(bot_id)
        return None
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 404:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Bot not found"
            )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete bot: {str(e)}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete bot: {str(e)}"
        )
