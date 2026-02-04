import logging
import base64
import time
import json
from typing import Dict, Any, Optional
from openai import OpenAI
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
        self.api_key = api_key or settings.OPENAI_API_KEY
        self.model_id = settings.OPENAI_MODEL
        
        if not self.api_key:
            raise ValueError("OPENAI_API_KEY must be set in environment or config")
            
        self.client = OpenAI(api_key=self.api_key)
        self._last_request_time = 0
    
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
            
            # Call OpenAI
            response = self.client.chat.completions.create(
                model=self.model_id,
                messages=messages,
                response_format=response_format,
                temperature=0.1,
                max_tokens=500  # Reduced for faster responses
            )
            
            processing_time = time.time() - start_time
            
            # Extract content and parse
            analysis_text = response.choices[0].message.content
            parsed_analysis = json.loads(analysis_text)
            parsed_analysis["processing_time"] = processing_time
            parsed_analysis["api"] = "openai-gpt4o"
            
            return parsed_analysis
                
        except Exception as e:
            logger.error(f"Error analyzing frame with OpenAI: {e}")
            return {
                "error": str(e),
                "processing_time": time.time() - start_time,
                "api": "openai-gpt4o"
            }
    
    def _build_analysis_prompt(
        self,
        audio_transcript: Optional[str],
        previous_context: Optional[Dict[str, Any]]
    ) -> str:
        """Build the analysis prompt for HIPAA compliance and medical interpreter QA."""
        prompt = """Analyze medical consultation. Return JSON:
{
  "person_count": number,
  "required_roles_present": {"patient": bool, "doctor": bool, "interpreter": bool},
  "unauthorized_persons_detected": bool,
  "unauthorized_persons_details": string,
  "hipaa_compliance": {
    "privacy_violations": bool,
    "environment_secure": bool,
    "compliance_score": number,
    "violations": string[]
  },
  "interpreter_qa": {
    "professionalism_score": number,
    "is_present": bool,
    "is_engaged": bool,
    "issues": string[]
  },
  "environment_analysis": {
    "is_private": bool,
    "is_professional": bool,
    "professionalism_note": string,
    "distractions": string[],
    "background_activity": string
  },
  "discussion_summary": string,
  "noise_detection": {"detected": bool, "description": string}
}

Check: person count, roles (patient/doctor/interpreter), privacy violations, environment professionalism, discussion summary, noise.
"""
        
        if audio_transcript:
            prompt += f"\nAUDIO TRANSCRIPT:\n{audio_transcript}\n"
        
        if previous_context:
            prompt += f"\nPREVIOUS CONTEXT:\n{previous_context}\n"
        
        return prompt
