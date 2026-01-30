from pydantic_settings import BaseSettings
from typing import Optional


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
    
    # Google Gemini API Configuration
    GEMINI_API_KEY: Optional[str] = None
    GEMINI_MODEL: str = "gemini-2.0-flash-exp"  # Use gemini-2.0-flash-exp or gemini-1.5-pro
    
    # Gemini Live API (real-time multimodal over WebSocket)
    GEMINI_LIVE_MODEL: str = "gemini-2.5-flash-native-audio-preview-12-2025"
    
    # Public WebSocket URL for Recall.ai to connect to (e.g. wss://your-domain.com/ws/recall)
    PUBLIC_WS_URL: Optional[str] = None
    
    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()
