from pydantic import BaseModel, HttpUrl, Field
from typing import Optional, Literal, List


class CreateBotRequest(BaseModel):
    """Request model for creating a meeting bot."""
    meeting_url: HttpUrl = Field(..., description="URL of the meeting to join")
    bot_name: Optional[str] = Field(
        default=None,
        description="Name for the bot (appears as participant name in the meeting)"
    )
    video_layout: Literal["speaker_view", "gallery_view_v2"] = Field(
        default="gallery_view_v2",
        description="Video layout: speaker_view shows only active speaker, gallery_view_v2 shows all participants"
    )
    auto_leave: bool = Field(
        default=True,
        description="Whether bot should automatically leave when meeting ends"
    )
    stream_key: Optional[str] = Field(
        default=None,
        description="Custom stream key for RTMP. If not provided, will be auto-generated"
    )
    events: Optional[List[str]] = Field(
        default=None,
        description="WebSocket events for live bot only (e.g. audio_mixed_raw.data, transcript.data, video_separate_png.data)"
    )


class BotResponse(BaseModel):
    """Response model for bot information."""
    id: str
    status: str
    bot_name: Optional[str] = None
    stream_key: Optional[str] = None
    meeting_url: Optional[str] = None
    meeting_metadata: Optional[dict] = None
    created_at: Optional[str] = None
    error_message: Optional[str] = None


class BotStatusResponse(BaseModel):
    """Detailed bot status response."""
    id: str
    status: str
    bot_name: Optional[str] = None
    meeting_url: Optional[str] = None
    meeting_metadata: Optional[dict] = None
    recording: Optional[dict] = None
    created_at: Optional[str] = None
    error_message: Optional[str] = None
