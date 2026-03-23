import logging
import time
import numpy as np
from collections import deque
from typing import List, Optional, Dict, Tuple, Any

logger = logging.getLogger(__name__)

class AudioBuffer:
    """
    Rolling buffer for raw PCM audio data from Recall.ai.
    Stores audio chunks with timestamps for precise slicing.
    """
    
    def __init__(self, max_seconds: int = 60, sample_rate: int = 16000, channels: int = 1):
        self.sample_rate = sample_rate
        self.channels = channels
        self.bytes_per_sample = 2  # s16le
        self.max_seconds = max_seconds
        
        # Buffer of (timestamp, chunk_bytes)
        self.buffer = deque(maxlen=int(max_seconds * 10))  # Assuming ~10 chunks per second
        
    def add_chunk(self, chunk: bytes, timestamp: Optional[float] = None):
        """Add a raw PCM chunk to the buffer."""
        if timestamp is None:
            timestamp = time.time()
        self.buffer.append((timestamp, chunk))
        
    def get_slice(self, start_time: float, end_time: float) -> bytes:
        """
        Extract an audio slice within the given time window.
        
        Args:
            start_time: Start timestamp (Unix time)
            end_time: End timestamp (Unix time)
            
        Returns:
            Concatenated bytes for the requested window.
        """
        if not self.buffer:
            return b""
            
        slice_chunks = []
        for ts, chunk in self.buffer:
            # Simple chunk-level selection
            # For more precision, we'd need to slice individual chunks
            if start_time <= ts <= end_time:
                slice_chunks.append(chunk)
            elif ts > end_time:
                break
                
        return b"".join(slice_chunks)

class AudioValidator:
    """
    Analyzes audio slices for compliance validation.
    Detects speech, noise, and overlaps.
    """
    
    @staticmethod
    def analyze_slice(audio_data: bytes, sample_rate: int = 16000) -> Dict[str, Any]:
        """
        Perform basic signal analysis on an audio slice.
        """
        if not audio_data:
            return {
                "error": "No audio data",
                "speech_ratio": 0.0,
                "noise_level": 0.0,
                "is_silent": True
            }
            
        # Convert to numpy for analysis
        samples = np.frombuffer(audio_data, dtype=np.int16).astype(np.float32)
        
        if len(samples) == 0:
            return {"error": "Empty samples", "speech_ratio": 0.0}
            
        # Calculate RMS energy
        rms = np.sqrt(np.mean(samples**2))
        
        # Simple threshold-based speech vs noise detection
        # Higher RMS values typically indicate speech or significant noise
        # This is a heuristic; production systems would use a VAD model
        threshold = 500.0  # Empirical threshold for speech in s16le
        speech_indices = np.abs(samples) > threshold
        speech_ratio = np.mean(speech_indices)
        
        # Detect background noise level (average of non-speech segments)
        noise_samples = samples[~speech_indices]
        if len(noise_samples) > 0:
            noise_level = np.sqrt(np.mean(noise_samples**2))
        else:
            noise_level = 0.0
            
        return {
            "rms": float(rms),
            "speech_ratio": float(speech_ratio),
            "noise_level": float(noise_level),
            "is_silent": rms < 50.0,
            "findings": AudioValidator._generate_findings(speech_ratio, noise_level)
        }
        
    @staticmethod
    def _generate_findings(speech_ratio: float, noise_level: float) -> str:
        """Generate human-readable findings based on audio analysis."""
        findings = []
        if speech_ratio > 0.8:
            findings.append("Continuous speech detected")
        elif speech_ratio < 0.2:
            findings.append("Low speech activity or heavy silence")
            
        if noise_level > 1000.0:
            findings.append("High background noise detected")
        elif noise_level > 500.0:
            findings.append("Moderate background noise present")
            
        return "; ".join(findings) if findings else "Normal audio characteristics"
