"""
RTMP Stream Capture Module
Captures video stream directly from RTMP for real-time analysis.
Streams video directly to Video Intelligence API without frame extraction.
"""
import asyncio
import logging
import subprocess
from typing import AsyncIterator, Optional

logger = logging.getLogger(__name__)


class RTMPStreamCapture:
    """
    Capture video stream directly from RTMP.
    Streams video to Video Intelligence API without extracting individual frames.
    """
    
    def __init__(self, rtmp_url: str, fps: int = 1):
        """
        Initialize RTMP stream capture.
        
        Args:
            rtmp_url: RTMP stream URL (e.g., rtmp://host:port/app/stream_key)
            fps: Not used for direct streaming (kept for compatibility)
        """
        self.rtmp_url = rtmp_url
        self.fps = fps
        self.process: Optional[subprocess.Popen] = None
        self.audio_process: Optional[subprocess.Popen] = None
    
    async def capture_frames(self) -> AsyncIterator[bytes]:
        """
        Capture frames from RTMP stream as JPEG bytes for analysis.
        
        Yields:
            JPEG-encoded frame bytes
        """
        # FFmpeg command to capture frames from RTMP stream
        ffmpeg_cmd = [
            'ffmpeg',
            '-i', self.rtmp_url,
            '-vf', f'fps={self.fps}',
            '-f', 'image2pipe',
            '-vcodec', 'mjpeg',
            '-q:v', '2',  # Quality (2-31, lower is better)
            '-'  # Output to stdout
        ]
        
        try:
            self.process = subprocess.Popen(
                ffmpeg_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                bufsize=10**8
            )
            
            # Read frames from stdout
            frame_buffer = b''
            jpeg_start = b'\xff\xd8'  # JPEG start marker
            jpeg_end = b'\xff\xd9'    # JPEG end marker
            
            while True:
                chunk = self.process.stdout.read(8192)
                if not chunk:
                    if self.process.poll() is not None:
                        break
                    await asyncio.sleep(0.01)
                    continue
                
                frame_buffer += chunk
                
                # Extract complete JPEG frames
                while True:
                    start_idx = frame_buffer.find(jpeg_start)
                    if start_idx == -1:
                        break
                    
                    end_idx = frame_buffer.find(jpeg_end, start_idx)
                    if end_idx == -1:
                        break
                    
                    # Extract complete frame
                    frame = frame_buffer[start_idx:end_idx + 2]
                    frame_buffer = frame_buffer[end_idx + 2:]
                    
                    if len(frame) > 100:  # Valid frame size check
                        yield frame
                        
        except Exception as e:
            logger.error(f"Error capturing frames from RTMP stream: {e}")
            raise
        finally:
            if self.process:
                self.process.terminate()
                self.process.wait()
    
    async def capture_audio(self) -> AsyncIterator[bytes]:
        """
        Capture audio from RTMP stream for disturbance detection.
        
        Yields:
            Audio chunk bytes (PCM format)
        """
        # FFmpeg command to capture audio
        ffmpeg_cmd = [
            'ffmpeg',
            '-i', self.rtmp_url,
            '-vn',  # No video
            '-acodec', 'pcm_s16le',  # PCM 16-bit little-endian
            '-ar', '16000',  # Sample rate 16kHz
            '-ac', '1',  # Mono
            '-f', 's16le',  # Raw PCM format
            '-'  # Output to stdout
        ]
        
        try:
            self.audio_process = subprocess.Popen(
                ffmpeg_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                bufsize=10**8
            )
            
            # Read audio chunks (1 second = 16000 samples * 2 bytes = 32000 bytes)
            chunk_size = 32000  # 1 second of audio
            while True:
                chunk = self.audio_process.stdout.read(chunk_size)
                if not chunk:
                    if self.audio_process.poll() is not None:
                        break
                    await asyncio.sleep(0.01)
                    continue
                
                yield chunk
                
        except Exception as e:
            logger.error(f"Error capturing audio from RTMP stream: {e}")
            raise
        finally:
            if self.audio_process:
                self.audio_process.terminate()
                self.audio_process.wait()
    
    async def capture_raw_video(self) -> AsyncIterator[bytes]:
        """
        Capture video stream directly from RTMP and format for Video Intelligence API.
        
        Video Intelligence API Streaming expects fragmented MP4 format.
        This method streams the RTMP directly without extracting frames.
        
        Yields:
            Video chunk bytes in fragmented MP4 format
        """
        # FFmpeg command to capture and format video for Video Intelligence API
        # Using fragmented MP4 (fmp4) which is what Video Intelligence API expects
        ffmpeg_cmd = [
            'ffmpeg',
            '-i', self.rtmp_url,
            '-c:v', 'libx264',  # H.264 codec
            '-preset', 'ultrafast',  # Fast encoding for real-time
            '-tune', 'zerolatency',  # Low latency
            '-g', '30',  # GOP size (keyframe every 30 frames)
            '-f', 'mp4',  # MP4 container
            '-movflags', 'frag_keyframe+empty_moov',  # Fragmented MP4 for streaming
            '-frag_duration', '1',  # 1 second fragments
            '-'  # Output to stdout
        ]
        
        try:
            self.process = subprocess.Popen(
                ffmpeg_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                bufsize=10**8
            )
            
            # Read chunks - Video Intelligence API works best with ~1MB chunks
            chunk_size = 1024 * 1024  # 1MB chunks for better API performance
            while True:
                chunk = self.process.stdout.read(chunk_size)
                if not chunk:
                    if self.process.poll() is not None:
                        break
                    await asyncio.sleep(0.01)
                    continue
                
                yield chunk
                
        except Exception as e:
            logger.error(f"Error capturing video stream from RTMP: {e}")
            # Log stderr for debugging
            if self.process and self.process.stderr:
                stderr_output = self.process.stderr.read().decode('utf-8', errors='ignore')
                if stderr_output:
                    logger.error(f"FFmpeg stderr: {stderr_output}")
            raise
        finally:
            if self.process:
                self.process.terminate()
                self.process.wait()
    
    def stop(self):
        """Stop the capture process."""
        if self.process:
            self.process.terminate()
            self.process.wait()
            self.process = None
        if self.audio_process:
            self.audio_process.terminate()
            self.audio_process.wait()
            self.audio_process = None
