from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional
from pathlib import Path


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    # Recall.ai API Configuration
    RECALL_AI_API_KEY: str
    RECALL_AI_BASE_URL: str = "https://us-west-2.recall.ai/api/v1"
    
    # Server Configuration
    SERVER_HOST: str = "0.0.0.0"
    SERVER_PORT: int = 8000
    
    # RTMP Configuration
    RTMP_HOST: str = "localhost"
    RTMP_PORT: int = 1935
    RTMP_APPLICATION: str = "stream"  # nginx-rtmp uses "stream" application
    RTMP_STREAM_KEY_PREFIX: str = "meeting"
    
    # Public URL for RTMP (needed for Recall.ai callback)
    # Use ngrok or similar for local development: https://your-ngrok-url.ngrok.io
    PUBLIC_RTMP_URL: Optional[str] = None
    
    # Google Cloud Video Intelligence API Configuration
    GOOGLE_CLOUD_PROJECT_ID: Optional[str] = None
    GOOGLE_APPLICATION_CREDENTIALS: Optional[str] = None  # Path to service account JSON (optional)
    GOOGLE_CLOUD_API_KEY: Optional[str] = None  # API key for Video Intelligence API (alternative to service account)
    GOOGLE_CLOUD_LOCATION: str = "us-central1"  # Default location for Video Intelligence API
    
    # Public WebSocket URL for Recall.ai to connect to (e.g. wss://your-domain.com/ws/recall)
    PUBLIC_WS_URL: Optional[str] = None
    
  
    # OpenAI configuration (for GPT vision/text analysis)
    OPENAI_API_KEY: Optional[str] = None
    OPENAI_MODEL: Optional[str] = "gpt-4o"

    # Transcription Provider Settings
    TRANSCRIPTION_PROVIDER: str = "recallai_streaming"  # Options: recallai_streaming, gladia, assembly_ai
    GLADIA_API_KEY: Optional[str] = None
    ASSEMBLY_AI_API_KEY: Optional[str] = None
    
    model_config = SettingsConfigDict(
        env_file=(".env", ".env.local"),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=True
    )

    @field_validator("PUBLIC_WS_URL", mode="before")
    @classmethod
    def strip_ws_url(cls, v):
        if isinstance(v, str):
            return v.strip()
        return v


settings = Settings()
