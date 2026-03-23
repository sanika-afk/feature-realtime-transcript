import logging
import base64
import time
import json
import asyncio
import os
from typing import Dict, Any, Optional, List
try:
    from openai import OpenAI
except Exception:
    OpenAI = None
from app.config import settings

logger = logging.getLogger(__name__)

class OpenAIClient:
    """Client for OpenAI GPT-4o vision analysis."""
    
    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize OpenAI client.
        
        Args:
            api_key: OpenAI API key (or from settings)
        """
        # Prefer explicit param, then settings, then environment variable
        self.api_key = api_key or getattr(settings, "OPENAI_API_KEY", None) or os.environ.get("OPENAI_API_KEY")
        self.model_id = getattr(settings, "OPENAI_MODEL", None) or os.environ.get("OPENAI_MODEL", "gpt-4o")

        if not self.api_key:
            raise ValueError("OPENAI_API_KEY must be set in environment or config")

        if OpenAI is None:
            raise RuntimeError("openai SDK not installed or importable")

        self.client = OpenAI(api_key=self.api_key)
        self._last_request_time = 0

    async def _call_with_retry(self, func, *args, **kwargs):
        """
        Execute an OpenAI API call with exponential backoff for transient errors.
        """
        max_retries = 3
        base_delay = 1.0
        
        for attempt in range(max_retries):
            try:
                return await asyncio.to_thread(func, *args, **kwargs)
            except Exception as e:
                error_msg = str(e).lower()
                
                # Check for fatal errors that should NOT be retried
                if "insufficient_quota" in error_msg:
                    raise  # Let the caller handle this specific error
                if "invalid_api_key" in error_msg:
                    raise
                    
                # Retry on rate limits (non-quota) or server errors
                if "rate limit" in error_msg or "500" in error_msg or "503" in error_msg:
                    if attempt < max_retries - 1:
                        delay = base_delay * (2 ** attempt)
                        logger.warning(f"[OPENAI] Transient error: {e}. Retrying in {delay}s...")
                        await asyncio.sleep(delay)
                        continue
                
                # Re-raise other errors
                raise
    
    async def analyze_frame(
        self,
        frame_bytes: bytes,
        audio_transcript: Optional[str] = None,
        previous_context: Optional[Dict[str, Any]] = None,
        mime_type: str = "image/png"
    ) -> Dict[str, Any]:
        """
        Analyze a single video frame using GPT-4o Vision.
        """
        start_time = time.time()
        
        # Build prompt
        prompt_text = self._build_analysis_prompt(audio_transcript, previous_context)
        
        # Check cooldown to prevent quota exhaustion
        current_time = time.time()
        cooldown_period = 2.0 # seconds - reduced for faster responses
        
        if current_time - self._last_request_time < cooldown_period:
            logger.info("[OPENAI] Skipping analysis: Throttled by cooldown (%.1fs remaining)", 
                        cooldown_period - (current_time - self._last_request_time))
            return {
                "error": "Throttled by cooldown",
                "person_count": None,
                "hipaa_compliance": {"compliance_score": None, "violations": ["Throttled"]}
            }
        
        self._last_request_time = current_time

        # Encode image to base64
        base64_image = base64.b64encode(frame_bytes).decode('utf-8')

        try:
            # Prepare messages for GPT-4o
            messages = [
                {
                    "role": "system",
                    "content": "You are a medical consultation auditor analyzing a real-time stream. Continuously monitor the provided image and transcript for HIPAA compliance, professionalism, and discussion context. Return ONLY a structured JSON object."
                },
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt_text},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:{mime_type};base64,{base64_image}",
                                "detail": "low"
                            }
                        }
                    ]
                }
            ]
            
            # Response format for structured output
            response_format = { "type": "json_object" }
            
            # Call OpenAI with retry
            response = await self._call_with_retry(
                self.client.chat.completions.create,
                model=self.model_id,
                messages=messages,
                response_format=response_format,
                temperature=0.1,
                max_tokens=500
            )
            
            processing_time = time.time() - start_time
            
            # Extract content and parse
            analysis_text = response.choices[0].message.content
            parsed_analysis = json.loads(analysis_text)
            parsed_analysis["processing_time"] = processing_time
            parsed_analysis["api"] = "openai-gpt4o"
            
            return parsed_analysis
                
        except Exception as e:
            error_msg = str(e).lower()
            if "insufficient_quota" in error_msg:
                logger.error("[OPENAI] Quota Exceeded in analyze_frame: Please check billing/plan.")
                return {
                    "error": "QUOTA_EXCEEDED",
                    "analysis": {
                        "summary": "AI Analysis Paused: OpenAI Quota Exceeded.",
                        "error_type": "QUOTA_EXCEEDED"
                    },
                    "processing_time": time.time() - start_time,
                    "api": "openai-gpt4o"
                }

            logger.error(f"Error analyzing frame with OpenAI: {e}")
            return {
                "error": str(e),
                "processing_time": time.time() - start_time,
                "api": "openai-gpt4o"
            }
    
    async def analyze_compliance_segment(
        self,
        transcript_text: str,
        speaker_role: str,
        audio_findings: str,
        video_findings: str,
        frame: Optional[bytes] = None,
        mime_type: str = "image/png"
    ) -> Dict[str, Any]:
        """
        Perform speaker-aware compliance reasoning on a finalized transcript segment.
        Identifies mismatch between speaker role, audio activity, and visual context.
        """
        start_time = time.time()
        
        prompt = f"""
        Analyze this medical meeting segment for compliance and diarization accuracy.
        
        INPUT DATA:
        - Speaker Label: {speaker_role}
        - Transcript: "{transcript_text}"
        - Audio Analysis: {audio_findings}
        - Video Analysis: {video_findings}
        
        TASK:
        1. Identify if there is any mismatch between the speaker label, the audio activity, and the visual context.
        2. Flag unauthorized speakers (anyone not a Doctor, Patient, or Interpreter).
        3. Determine if the linguistic intent of the transcript matches the speaker's role.
        
        RETURN ONLY JSON:
        {{
          "error_type": "Omission | Addition | Noise | Unauthorized Speaker | Role Mismatch | None",
          "severity": "Critical | Major | Minor | None",
          "explanation": "Detailed reasoning for the finding",
          "confidence": 0-100
        }}
        """
        
        messages = [
            {"role": "system", "content": "You are a specialized medical compliance auditor. Provide structured reasoning based on audio, video, and transcript evidence."},
            {"role": "user", "content": []}
        ]
        
        messages[1]["content"].append({"type": "text", "text": prompt})
        
        if frame:
            base64_image = base64.b64encode(frame).decode('utf-8')
            messages[1]["content"].append({
                "type": "image_url",
                "image_url": {"url": f"data:{mime_type};base64,{base64_image}", "detail": "low"}
            })

        try:
            response = await self._call_with_retry(
                self.client.chat.completions.create,
                model=self.model_id,
                messages=messages,
                response_format={"type": "json_object"},
                temperature=0.1,
                max_tokens=300
            )
            
            result = json.loads(response.choices[0].message.content)
            result["processing_time"] = time.time() - start_time
            return result
        except Exception as e:
            error_msg = str(e).lower()
            if "insufficient_quota" in error_msg:
                logger.error("[OPENAI] Quota Exceeded in analyze_frame: Please check billing/plan.")
                return {
                    "error_type": "QUOTA_EXCEEDED",
                    "severity": "Critical",
                    "explanation": "OpenAI API Quota Exceeded. Compliance analysis is paused until billing is updated.",
                    "confidence": 0
                }
            
            logger.error(f"Error in compliance reasoning: {e}")
            return {
                "error_type": "None",
                "severity": "None",
                "explanation": f"Analysis failed: {str(e)}",
                "confidence": 0
            }

    async def analyze_interpretation_accuracy(
        self,
        doctor_text: str,
        interpreter_text: str,
        patient_text: Optional[str] = None,
        frame: Optional[bytes] = None,
        mime_type: str = "image/png"
    ) -> Dict[str, Any]:
        """
        Compare meaning between Doctor's source and Interpreter's target speech.
        Detects Omissions, Additions, Distortion, and Dosage/Timing mistakes.
        """
        start_time = time.time()
        
        prompt = f"""
        Compare the semantic meaning between the Doctor's statement and the Interpreter's translation.
        
        INPUT DATA:
        - Doctor's Sentence: "{doctor_text}"
        - Interpreter's Sentence: "{interpreter_text}"
        {f'- Patient Response: "{patient_text}"' if patient_text else ""}
        
        TASK:
        1. Compare MEANING, not just wording. Paraphrasing is acceptable if intent is preserved.
        2. Detect:
           - Omission: Missing critical info.
           - Addition: Extra medical info not in source.
           - Distortion: Meaning changed or misinterpreted context.
           - Dosage/Timing: WRONG DOSE, QUANTITY, OR SCHEDULE (CRITICAL).
        3. Classify Severity:
           - Critical: High medical risk (dosage error, wrong instruction, total omission of risk).
           - Major: Meaningful difference but lower risk.
           - Minor: Nuance change or slight phrasing difference.
           - None: Accurate interpretation.
        
        RETURN ONLY JSON:
        {{
          "issue_type": "Omission | Distortion | Addition | Dosage/Timing | None",
          "severity": "Critical | Major | Minor | None",
          "confidence": 0-100,
          "notes": "Specific details of what was missed, added, or changed"
        }}
        """
        
        messages = [
            {"role": "system", "content": "You are a medical interpretation auditor. Compare source and target speech for medical accuracy."},
            {"role": "user", "content": []}
        ]
        
        messages[1]["content"].append({"type": "text", "text": prompt})
        
        if frame:
            base64_image = base64.b64encode(frame).decode('utf-8')
            messages[1]["content"].append({
                "type": "image_url",
                "image_url": {"url": f"data:{mime_type};base64,{base64_image}", "detail": "low"}
            })

        try:
            response = await self._call_with_retry(
                self.client.chat.completions.create,
                model=self.model_id,
                messages=messages,
                response_format={"type": "json_object"},
                temperature=0.0,
                max_tokens=300
            )
            
            result = json.loads(response.choices[0].message.content)
            result["processing_time"] = time.time() - start_time
            return result
        except Exception as e:
            error_msg = str(e).lower()
            if "insufficient_quota" in error_msg:
                return {
                    "issue_type": "QUOTA_EXCEEDED",
                    "severity": "Critical",
                    "confidence": 0,
                    "notes": "OpenAI API Quota Exceeded. Check your billing details."
                }
            
            logger.error(f"Error in interpretation analysis: {e}")
            return {
                "issue_type": "None",
                "severity": "None",
                "confidence": 0,
                "notes": f"Analysis failed: {str(e)}"
            }

    async def verify_speaker_intent(self, text: str, context_history: List[str] = None) -> Dict[str, Any]:
        """
        Identify speaker role based on linguistic intent and medical context.
        """
        start_time = time.time()
        ctx = " ".join(context_history) if context_history else "No previous context"
        
        prompt = f"""
        Identify the role of the person speaking the current sentence.
        
        PREVIOUS CONTEXT: 
        {ctx}
        
        CURRENT SENTENCE:
        "{text}"
        
        ROLES DEFINITION:
        - Doctor: Asking clinical questions, giving medical instructions, prescribing.
        - Patient: Describing symptoms, internal feelings, medical history.
        - Interpreter: Relaying messages ("The doctor says...", "He says he has..."), translating.
        
        RETURN ONLY JSON:
        {{
          "identified_role": "Doctor | Patient | Interpreter",
          "confidence": 0-100,
          "intent": "e.g., Clinical inquiry, Symptom description, Message relaying",
          "reasoning": "Brief explanation"
        }}
        """
        
        try:
            response = await self._call_with_retry(
                self.client.chat.completions.create,
                model=self.model_id,
                messages=[
                    {"role": "system", "content": "You are a linguistic analyst for medical consultations."},
                    {"role": "user", "content": prompt}
                ],
                response_format={"type": "json_object"},
                temperature=0.0,
                max_tokens=200
            )
            
            result = json.loads(response.choices[0].message.content)
            result["processing_time"] = time.time() - start_time
            return result
        except Exception as e:
            logger.error(f"Error in speaker intent verification: {e}")
            return {"identified_role": "Unknown", "confidence": 0, "reasoning": str(e)}

    def _build_analysis_prompt(
        self,
        audio_transcript: Optional[str],
        previous_context: Optional[Dict[str, Any]]
    ) -> str:
        """Build the analysis prompt for medical consultation auditing."""
        prompt = """Analyze this medical consultation video frame and transcript for auditing purposes.
Return ONLY a structured JSON object with the following fields:
{
  "summary": "Concise summary of what is happening (1-2 sentences)",
  "risk_level": "Low | Medium | High",
  "confidence": number (0-100),
  "analysis": {
    "speaker_behavior": "Analysis of the speaker's conduct and tone",
    "context_correctness": "Whether the discussion matches the expected medical context",
    "unauthorized_presence": "Detection of any unauthorized persons or lack of required roles",
    "background_distractions": "Any visual or auditory distractions in the background",
    "compliance_risks": "Potential HIPAA or protocol violations detected",
    "person_count": number
  }
}

Analyze specifically:
1. Speaker behavior and professionalism.
2. Context correctness: Does what's being said align with the visual context?
3. Unauthorized presence: Are there people who shouldn't be there? Are mandatory participants present?
4. Background distractions: Any issues in the speaker's environment?
5. Compliance risks: Any obvious HIPAA or privacy concerns?
"""
        
        if audio_transcript:
            prompt += f"\nAUDIO TRANSCRIPT:\n{audio_transcript}\n"
        
        if previous_context:
            prompt += f"\nPREVIOUS CONTEXT:\n{previous_context}\n"
        
        return prompt
