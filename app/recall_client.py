import httpx
from typing import Dict, Any, Optional, List
from app.config import settings


class RecallAIClient:
    """Client for interacting with Recall.ai API."""
    
    def __init__(self):
        self.base_url = settings.RECALL_AI_BASE_URL
        self.api_key = settings.RECALL_AI_API_KEY
        self.headers = {
            "Authorization": f"Token {self.api_key}",
            "accept": "application/json",
            "content-type": "application/json"
        }
    
    async def create_bot(
        self,
        meeting_url: str,
        rtmp_url: str,
        video_layout: str = "gallery_view_v2",
        auto_leave: bool = True,
        bot_name: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Create a bot that joins a meeting and streams via RTMP.
        
        Args:
            meeting_url: URL of the meeting to join
            rtmp_url: RTMP endpoint URL where stream will be sent
            video_layout: "speaker_view" or "gallery_view_v2"
            auto_leave: Whether bot should leave when meeting ends
            bot_name: Name for the bot (appears as participant name)
            **kwargs: Additional bot configuration options
        
        Returns:
            Bot creation response from Recall.ai
        """
        payload = {
            "meeting_url": meeting_url,
            "recording_config": {
                "video_mixed_flv": {},
                "realtime_endpoints": [
                    {
                        "type": "rtmp",
                        "url": rtmp_url,
                        "events": ["video_mixed_flv.data"]
                    }
                ]
            },
            "video_layout": video_layout,
            "automatic_leave": {
                "waiting_room_timeout": 120,
                "noone_joined_timeout": 300,
                "everyone_left_timeout": 30
            } if auto_leave else None
        }
        
        # Add bot_name if provided
        if bot_name:
            payload["bot_name"] = bot_name
        
        # Add any additional configuration
        payload.update(kwargs)
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/bot/",
                headers=self.headers,
                json=payload,
                timeout=30.0
            )
            response.raise_for_status()
            return response.json()
    
    async def get_bot(self, bot_id: str) -> Dict[str, Any]:
        """Get bot status and details."""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/bot/{bot_id}/",
                headers=self.headers,
                timeout=30.0
            )
            response.raise_for_status()
            return response.json()
    
    async def list_bots(
        self,
        limit: int = 10,
        offset: int = 0
    ) -> Dict[str, Any]:
        """List all bots."""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/bot/",
                headers=self.headers,
                params={"limit": limit, "offset": offset},
                timeout=30.0
            )
            response.raise_for_status()
            return response.json()
    
    async def delete_bot(self, bot_id: str) -> Dict[str, Any]:
        """Delete/stop a bot."""
        async with httpx.AsyncClient() as client:
            response = await client.delete(
                f"{self.base_url}/bot/{bot_id}/",
                headers=self.headers,
                timeout=30.0
            )
            response.raise_for_status()
            return response.json()
