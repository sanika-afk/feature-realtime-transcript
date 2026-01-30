"""
Gemini Multimodal Live API client for real-time meeting analysis.
Uses WebSocket to send video frames (~1 FPS) and optional transcript to Gemini Live API.
Requires: pip install google-genai
"""
import asyncio
import logging
import time
from typing import AsyncIterator, Dict, Any, Optional, Callable, Awaitable

from app.config import settings

logger = logging.getLogger(__name__)

try:
    from google import genai
    from google.genai import types
    GENAI_AVAILABLE = True
except ImportError:
    GENAI_AVAILABLE = False
    genai = None
    types = None


# System instruction for real-time HIPAA / meeting analysis
DEFAULT_SYSTEM_INSTRUCTION = """You are analyzing a live medical consultation meeting for HIPAA compliance and quality.

For each video frame and any transcript you receive, provide brief real-time analysis in JSON:
{
  "person_count": <number visible>,
  "hipaa_ok": <true/false>,
  "compliance_notes": "<short note>",
  "interpreter_present": <true/false>,
  "environment_ok": <true/false>
}

Keep responses concise. If you see a potential issue, note it in compliance_notes."""


class GeminiLiveClient:
    """Client for Gemini Multimodal Live API (real-time video + text analysis)."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        system_instruction: Optional[str] = None,
    ):
        self.api_key = api_key or settings.GEMINI_API_KEY
        self.model = model or settings.GEMINI_LIVE_MODEL
        self.system_instruction = system_instruction or DEFAULT_SYSTEM_INSTRUCTION
        if not GENAI_AVAILABLE:
            raise RuntimeError("google-genai is required for Live API. Install with: pip install google-genai")
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY must be set for Live API")
        self._client = genai.Client(api_key=self.api_key)

    def _config(self) -> Dict[str, Any]:
        """Build session config. Do NOT add input_modalities — LiveConnectConfig rejects it."""
        return {
            "response_modalities": ["TEXT"],
            "system_instruction": self.system_instruction,
        }

    async def run_live_session(
        self,
        frame_iterator: AsyncIterator[bytes],
        transcript_iterator: Optional[AsyncIterator[str]] = None,
        analysis_callback: Optional[Callable[[Dict[str, Any]], Awaitable[None]]] = None,
    ) -> None:
        """
        Run a Live API session: send frames at ~1 FPS and optional transcript, stream analysis back.
        
        Args:
            frame_iterator: Async iterator yielding JPEG (or PNG) image bytes
            transcript_iterator: Optional async iterator yielding transcript text
            analysis_callback: Optional async callable(message_dict) for each analysis chunk
        """
        config = self._config()
        last_frame_time = 0.0
        min_frame_interval = 1.0  # 1 FPS for Gemini Live recommendation
        pending_frames: asyncio.Queue = asyncio.Queue(maxsize=2)
        pending_transcript: asyncio.Queue = asyncio.Queue(maxsize=10)

        async def feed_frames():
            try:
                async for frame_bytes in frame_iterator:
                    await pending_frames.put(frame_bytes)
            except asyncio.CancelledError:
                pass
            except Exception as e:
                logger.exception("Frame iterator error: %s", e)
            finally:
                await pending_frames.put(None)

        async def feed_transcript():
            if not transcript_iterator:
                await pending_transcript.put(None)
                return
            try:
                async for text in transcript_iterator:
                    if text and text.strip():
                        await pending_transcript.put(text.strip())
                await pending_transcript.put(None)
            except asyncio.CancelledError:
                pass
            except Exception as e:
                logger.exception("Transcript iterator error: %s", e)
            finally:
                try:
                    await pending_transcript.put(None)
                except Exception:
                    pass

        # Timeout waiting for first frame (Recall may not send video immediately or at all)
        FIRST_FRAME_TIMEOUT = 120.0

        async def session_loop():
            nonlocal last_frame_time
            # Start feeders so we can wait for the first frame before connecting
            frame_task = asyncio.create_task(feed_frames())
            transcript_task = asyncio.create_task(feed_transcript())
            try:
                logger.info("[GEMINI-BRIDGE] Waiting for first video frame (max %.0fs) ...", FIRST_FRAME_TIMEOUT)
                try:
                    first_frame = await asyncio.wait_for(pending_frames.get(), timeout=FIRST_FRAME_TIMEOUT)
                except asyncio.TimeoutError:
                    logger.warning("[GEMINI-BRIDGE] No video frame in %.0fs; Gemini not started. Check that frames are queued (see '[GEMINI-BRIDGE] Video frame queued' or 'Failed to decode').", FIRST_FRAME_TIMEOUT)
                    return
                if first_frame is None:
                    return  # stream ended before any frame
                logger.info("[GEMINI-BRIDGE] First frame received (%d bytes), connecting to Gemini Live ...", len(first_frame))

                GEMINI_CONNECT_TIMEOUT = 30.0
                cm = self._client.aio.live.connect(model=self.model, config=config)
                try:
                    session = await asyncio.wait_for(cm.__aenter__(), timeout=GEMINI_CONNECT_TIMEOUT)
                except asyncio.TimeoutError:
                    logger.warning("[GEMINI-BRIDGE] Gemini Live connection timed out after %.0fs (check API key and network).", GEMINI_CONNECT_TIMEOUT)
                    return
                except Exception as e:
                    logger.exception("[GEMINI-BRIDGE] Gemini Live connection failed: %s", e)
                    return
                try:
                    logger.info("[GEMINI-BRIDGE] Gemini Live session established.")
                    # Immediately send the first image so Gemini infers vision+text, not audio
                    await _send_media(session, first_frame)
                    sent_first_frame = len(first_frame) >= 1000  # True if we actually sent
                    last_frame_time = time.time()

                    receiver = asyncio.create_task(
                        _receive_loop(session, analysis_callback)
                    )
                    while True:
                        now = time.time()
                        if now - last_frame_time >= min_frame_interval:
                            try:
                                frame_bytes = await asyncio.wait_for(
                                    pending_frames.get(), timeout=0.5
                                )
                                if frame_bytes is None:
                                    break
                                await _send_media(session, frame_bytes)
                                sent_first_frame = True
                                last_frame_time = now
                            except asyncio.TimeoutError:
                                pass
                        if sent_first_frame:
                            try:
                                text = pending_transcript.get_nowait()
                                if text is None:
                                    break
                                if text:
                                    await _send_text(session, text)
                            except asyncio.QueueEmpty:
                                pass
                        await asyncio.sleep(0.1)
                    await _send_end_of_turn(session)
                    await receiver
                finally:
                    try:
                        await cm.__aexit__(None, None, None)
                    except Exception:
                        pass
            finally:
                frame_task.cancel()
                transcript_task.cancel()
                for t in (frame_task, transcript_task):
                    try:
                        await t
                    except asyncio.CancelledError:
                        pass

        await session_loop()


async def _send_media(session: Any, frame_bytes: bytes) -> None:
    """Send one image frame to Live API. Use correct MIME (PNG vs JPEG) and skip corrupted frames."""
    if len(frame_bytes) < 1000:
        return  # skip corrupted/tiny frames; Gemini Live is sensitive
    mime = "image/png" if frame_bytes.startswith(b"\x89PNG") else "image/jpeg"
    if types is not None:
        blob = types.Blob(data=frame_bytes, mime_type=mime)
        if hasattr(session, "send_realtime_input"):
            await session.send_realtime_input(media=blob)
        elif hasattr(session, "send"):
            await session.send(types.LiveClientRealtimeInput(media_chunks=[blob]), end_of_turn=False)
    else:
        if hasattr(session, "send"):
            await session.send({"media_chunks": [{"data": frame_bytes, "mime_type": mime}]}, end_of_turn=False)
    logger.info("[GEMINI-BRIDGE] Sent frame to Gemini (%d bytes, %s)", len(frame_bytes), mime)


async def _send_text(session: Any, text: str) -> None:
    if types is not None and hasattr(session, "send"):
        await session.send(types.LiveClientRealtimeInput(text=text), end_of_turn=False)
    elif hasattr(session, "send"):
        await session.send({"text": text}, end_of_turn=False)


async def _send_end_of_turn(session: Any) -> None:
    if types is not None and hasattr(session, "send"):
        await session.send(types.LiveClientRealtimeInput(), end_of_turn=True)
    elif hasattr(session, "send"):
        await session.send({}, end_of_turn=True)


async def _receive_loop(session: Any, callback: Optional[Callable]) -> None:
    try:
        async for event in session.receive():
            text = getattr(event, "text", None) or (event if isinstance(event, str) else None)
            if callback and text:
                await callback({"text": text, "raw": event})
    except asyncio.CancelledError:
        pass
    except Exception as e:
        logger.exception("Live API receive error: %s", e)
