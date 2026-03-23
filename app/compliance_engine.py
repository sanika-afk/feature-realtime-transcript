import logging
import asyncio
import time
from typing import Dict, Any, List, Optional
from app.audio_processor import AudioValidator, AudioBuffer
from app.speaker_detector import get_speaker_detector

logger = logging.getLogger(__name__)

class ComplianceEngine:
    """
    Coordinates speaker-aware compliance analysis.
    Triggered by finalized transcript entries.
    """
    
    def __init__(self, openai_client, audio_buffer: AudioBuffer, broadcast_callback):
        self.openai_client = openai_client
        self.audio_buffer = audio_buffer
        self.broadcast_callback = broadcast_callback
        self.speaker_detector = get_speaker_detector()
        
        # Buffers for Stage-3 Interpretation Check
        self.last_doctor_text: Optional[str] = None
        self.last_interpreter_text: Optional[str] = None
        self.last_doctor_timestamp: Optional[float] = None
        
    async def analyze_segment(
        self, 
        transcript_entry: Dict[str, Any], 
        recent_frames: List[tuple]
    ):
        """
        Asynchronously analyze a transcript segment with audio and video evidence.
        Includes Layer 3 Semantic Audit.
        """
        try:
            text = transcript_entry.get("text", "")
            speaker = transcript_entry.get("speaker", "Unknown")
            start_time = transcript_entry.get("start_time")
            end_time = transcript_entry.get("end_time")
            
            if not start_time or not end_time:
                logger.warning("[COMPLIANCE] Missing timestamps for segment: %s", text[:30])
                end_time = time.time()
                start_time = end_time - 3.0
                
            logger.info("[COMPLIANCE] Analyzing segment: [%s] %s", speaker, text[:50])
            
            # Layer 3: AI-Driven Speaker Intent Verification
            if self.openai_client and text:
                # Use a sliding window of the last 3 transcript entries as context
                from app.routes.live import _transcript_history
                context = [e["text"] for e in _transcript_history[-3:]] if '_transcript_history' in globals() else []
                
                intent_result = await self.openai_client.verify_speaker_intent(text, context)
                ai_role = intent_result.get("identified_role", "Unknown")
                
                if ai_role != "Unknown" and ai_role != speaker:
                    logger.warning("[LAYER-3] Speaker Mismatch: Heuristic says %s, AI Intent says %s", speaker, ai_role)
                    # We can use this to adjust the "speaker" for subsequent analysis
                    # speaker = ai_role # Optional: switch to AI role if confidence is high
                    await self.broadcast_callback({
                        "event": "ai_role_correction",  # A new event name
                        "data": {
                            "text": text,               # The same sentence
                            "ai_role": ai_role          # The corrected role (e.g., Patient)
                        }
                    })
            # 1. State Tracking for Interpretation Verification
            # If Doctor speaks, buffer it
            if speaker.upper() == "DOCTOR":
                self.last_doctor_text = text
                self.last_doctor_timestamp = end_time
                # self.last_interpreter_text = None # Don't reset, allowing multiple interpreter segments
                
            # If Interpreter speaks, link to Doctor
            elif speaker.upper().startswith("INTERPRETER"):
                self.last_interpreter_text = text
                
                # Check for Accuracy (Doctor -> Interpreter sequence)
                if self.last_doctor_text and (end_time - self.last_doctor_timestamp < 45): # Increased window to 45s
                    # Trigger Stage 3 Async LLM Call
                    asyncio.create_task(self._run_semantic_verification(
                        doctor_text=self.last_doctor_text,
                        interpreter_text=text,
                        timestamp=end_time,
                        frame=recent_frames[-1][1] if recent_frames else None
                    ))

            # 2. Basic Audio/Video Validation
            audio_slice = self.audio_buffer.get_slice(start_time, end_time)
            audio_results = AudioValidator.analyze_slice(audio_slice)
            selected_frames = self._select_frames_in_window(recent_frames, start_time, end_time)
            video_findings = self._analyze_video_context(selected_frames, speaker)
            
            # 3. Compliance Reasoning (Unauthorized Speakers / Context Mismatch)
            if self.openai_client:
                compliance_result = await self.openai_client.analyze_compliance_segment(
                    transcript_text=text,
                    speaker_role=speaker,
                    audio_findings=audio_results.get("findings", "No audio"),
                    video_findings=video_findings,
                    frame=selected_frames[0][1] if selected_frames else None
                )
                
                # Emit General Compliance Event
                await self.broadcast_callback({
                    "event": "compliance_event",
                    "data": {
                        "timestamp": time.strftime("%H:%M:%S", time.localtime(end_time)),
                        "speaker": speaker,
                        "issue_type": compliance_result.get("error_type", "None"),
                        "severity": compliance_result.get("severity", "Low"),
                        "explanation": compliance_result.get("explanation", ""),
                        "confidence": compliance_result.get("confidence", 0)
                    }
                })

        except Exception as e:
            logger.exception("[COMPLIANCE] Error in segment analysis: %s", e)

    async def _run_semantic_verification(self, doctor_text: str, interpreter_text: str, timestamp: float, frame: Optional[bytes]):
        """Runs the deep Stage-3 semantic comparison using OpenAI."""
        if not self.openai_client:
            return

        try:
            # Pass patient context if available for better verification
            result = await self.openai_client.analyze_interpretation_accuracy(
                doctor_text=doctor_text,
                interpreter_text=interpreter_text,
                frame=frame
            )
            
            # Broadcast the interpretation event specifically
            await self.broadcast_callback({
                "event": "interpretation_accuracy",
                "data": {
                    "timestamp": time.strftime("%H:%M:%S", time.localtime(timestamp)),
                    "doctor_text": doctor_text,
                    "interpreter_text": interpreter_text,
                    "issue_type": result.get("issue_type", "None"),
                    "severity": result.get("severity", "None"),
                    "confidence": result.get("confidence", 0),
                    "notes": result.get("notes", "")
                }
            })
            logger.info("[SEMANTIC] Analysis completed: %s", result.get("issue_type"))
            
        except Exception as e:
            logger.error("[SEMANTIC] Error in accuracy check: %s", e)

    def _select_frames_in_window(self, frames: List[tuple], start: float, end: float, limit: int = 2) -> List[tuple]:
        """Select up to 'limit' frames within the time window."""
        matches = [f for f in frames if start <= f[0] <= end]
        if not matches and frames:
            # Fallback to closest frame if window is empty
            closest = min(frames, key=lambda f: abs(f[0] - end))
            matches = [closest]
            
        return matches[:limit]

    def _analyze_video_context(self, frames: List[tuple], speaker: str) -> str:
        """Basic visual context analysis (Heuristics or Vision call placeholder)."""
        if not frames:
            return "No video frames available for this segment"
        return f"Analyzing {len(frames)} frames for speaker {speaker}"

    def _check_speaker_matching(self, speaker: str, audio_results: Dict, video_findings: str) -> Dict[str, Any]:
        """Verify if the claimed speaker matches audio/video activity."""
        is_unknown = speaker == "Unknown"
        is_silent = audio_results.get("is_silent", False)
        
        status = "Match"
        if is_unknown:
            status = "Unauthorized Speaker (Label Unknown)"
        elif is_silent and not is_unknown:
            status = "Speaker Mismatch (No Audio Activity)"
            
        return {
            "status": status,
            "is_unauthorized": is_unknown or status != "Match"
        }
