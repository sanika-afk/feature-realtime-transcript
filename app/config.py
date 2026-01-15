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
    
    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()
