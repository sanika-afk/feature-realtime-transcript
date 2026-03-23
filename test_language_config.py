import asyncio
import json
from unittest.mock import MagicMock, patch
from app.recall_client import RecallAIClient
from app.models import CreateBotRequest

async def test_bot_creation_payload():
    client = RecallAIClient()
    client.api_key = "test_key"
    
    # Mock httpx.AsyncClient.post
    mock_response = MagicMock()
    mock_response.status_code = 201
    mock_response.json.return_value = {"id": "test_bot_id", "status": "joining"}
    mock_response.raise_for_status = MagicMock()

    with patch("httpx.AsyncClient.post", return_value=mock_response) as mock_post:
        # Test 1: Default (None/Auto-detect)
        request = CreateBotRequest(meeting_url="https://meet.google.com/abc-defg-hij")
        
        await client.create_bot(
            meeting_url=str(request.meeting_url),
            rtmp_url="rtmp://localhost/live/test",
            transcription_language=request.transcription_language
        )
        
        # Check payload
        args, kwargs = mock_post.call_args
        payload = kwargs["json"]
        lang = payload["recording_config"]["transcript"]["provider"]["recallai_streaming"]["language"]
        print(f"Test 1 (Default): language = {lang}")
        assert lang is None
        
        # Test 2: Explicit language
        request_hi = CreateBotRequest(
            meeting_url="https://meet.google.com/abc-defg-hij",
            transcription_language="hi-IN"
        )
        
        await client.create_bot(
            meeting_url=str(request_hi.meeting_url),
            rtmp_url="rtmp://localhost/live/test",
            transcription_language=request_hi.transcription_language
        )
        
        args, kwargs = mock_post.call_args
        payload = kwargs["json"]
        lang = payload["recording_config"]["transcript"]["provider"]["recallai_streaming"]["language"]
        print(f"Test 2 (Explicit 'hi-IN'): language = {lang}")
        assert lang == "hi-IN"

        # Test 3: WebSocket Bot
        await client.create_bot_with_websocket(
            meeting_url="https://meet.google.com/abc-defg-hij",
            websocket_url="wss://example.com/ws",
            language=None
        )
        
        args, kwargs = mock_post.call_args
        payload = kwargs["json"]
        lang = payload["recording_config"]["transcript"]["provider"]["recallai_streaming"]["language"]
        print(f"Test 3 (WebSocket Default): language = {lang}")
        assert lang is None

    print("\n✅ All transcription language tests passed!")

if __name__ == "__main__":
    asyncio.run(test_bot_creation_payload())
