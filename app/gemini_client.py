"""
Google Gemini API Client for Multimodal Analysis
Analyzes video frames and audio for HIPAA compliance and medical interpreter QA.
"""
import asyncio
import logging
import base64
import time
from typing import AsyncIterator, Dict, Any, Optional, List
import httpx
from app.config import settings

logger = logging.getLogger(__name__)


class GeminiClient:
    """Client for Google Gemini API multimodal analysis."""
    
    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize Gemini client.
        
        Args:
            api_key: Gemini API key (or from settings)
        """
        self.api_key = api_key or settings.GEMINI_API_KEY
        self.model = settings.GEMINI_MODEL
        self.base_url = "https://generativelanguage.googleapis.com/v1beta"
        
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY must be set in environment or config")
    
    async def analyze_frame(
        self,
        frame_bytes: bytes,
        audio_transcript: Optional[str] = None,
        previous_context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Analyze a single video frame using Gemini multimodal API.
        
        Args:
            frame_bytes: JPEG frame bytes
            audio_transcript: Optional audio transcript for this frame period
            previous_context: Previous analysis context for continuity
        
        Returns:
            Analysis results dictionary
        """
        start_time = time.time()
        
        # Encode frame to base64
        frame_base64 = base64.b64encode(frame_bytes).decode('utf-8')
        
        # Build prompt for HIPAA compliance and medical interpreter QA
        prompt = self._build_analysis_prompt(audio_transcript, previous_context)
        
        # Prepare request payload
        payload = {
            "contents": [{
                "parts": [
                    {
                        "text": prompt
                    },
                    {
                        "inline_data": {
                            "mime_type": "image/jpeg",
                            "data": frame_base64
                        }
                    }
                ]
            }],
            "generationConfig": {
                "temperature": 0.1,  # Low temperature for consistent analysis
                "topK": 40,
                "topP": 0.95,
                "maxOutputTokens": 2048,
            }
        }
        
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                url = f"{self.base_url}/models/{self.model}:generateContent?key={self.api_key}"
                response = await client.post(url, json=payload)
                response.raise_for_status()
                
                result = response.json()
                processing_time = time.time() - start_time
                
                # Extract analysis from response
                analysis_text = ""
                if "candidates" in result and len(result["candidates"]) > 0:
                    candidate = result["candidates"][0]
                    if "content" in candidate and "parts" in candidate["content"]:
                        for part in candidate["content"]["parts"]:
                            if "text" in part:
                                analysis_text += part["text"]
                
                # Parse structured response
                parsed_analysis = self._parse_analysis_response(analysis_text)
                parsed_analysis["processing_time"] = processing_time
                parsed_analysis["api"] = "gemini"
                
                return parsed_analysis
                
        except Exception as e:
            logger.error(f"Error analyzing frame with Gemini: {e}")
            return {
                "error": str(e),
                "processing_time": time.time() - start_time,
                "api": "gemini"
            }
    
    def _build_analysis_prompt(
        self,
        audio_transcript: Optional[str],
        previous_context: Optional[Dict[str, Any]]
    ) -> str:
        """Build the analysis prompt for HIPAA compliance and medical interpreter QA."""
        prompt = """You are analyzing a medical consultation video for HIPAA compliance and medical interpreter quality assurance.

CRITICAL REQUIREMENTS:
1. There must be exactly 3 people present: Patient, Doctor, and Medical Interpreter
2. No unauthorized persons should be visible or audible
3. The environment must be private and secure
4. The medical interpreter must maintain professionalism

ANALYZE THIS FRAME AND PROVIDE A JSON RESPONSE WITH THE FOLLOWING STRUCTURE:
{
  "person_count": <number of people visible>,
  "required_roles_present": {
    "patient": <true/false>,
    "doctor": <true/false>,
    "interpreter": <true/false>
  },
  "unauthorized_persons_detected": <true/false>,
  "unauthorized_persons_details": "<description if any>",
  "hipaa_compliance": {
    "privacy_violations": <true/false>,
    "environment_secure": <true/false>,
    "compliance_score": <0-100>,
    "violations": ["<list of any violations>"]
  },
  "interpreter_qa": {
    "professionalism_score": <0-100>,
    "is_present": <true/false>,
    "is_engaged": <true/false>,
    "issues": ["<list of any issues>"]
  },
  "environment_analysis": {
    "is_private": <true/false>,
    "distractions": ["<list of distractions>"],
    "background_activity": "<description>"
  }
}"""
        
        if audio_transcript:
            prompt += f"\n\nAUDIO TRANSCRIPT FOR THIS PERIOD:\n{audio_transcript}\n\nAlso analyze for:\n- Third-party disturbances (baby crying, pet sounds, etc.)\n- Background conversations\n- Unauthorized audio presence"
        
        if previous_context:
            prompt += f"\n\nPREVIOUS CONTEXT:\n{previous_context}\n\nMaintain continuity and track changes."
        
        prompt += "\n\nProvide ONLY valid JSON, no additional text."
        
        return prompt
    
    def _parse_analysis_response(self, response_text: str) -> Dict[str, Any]:
        """Parse the Gemini response into structured data."""
        import json
        import re
        
        try:
            # Try to extract JSON from response
            json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
            if json_match:
                json_str = json_match.group(0)
                return json.loads(json_str)
        except Exception as e:
            logger.warning(f"Could not parse JSON from Gemini response: {e}")
        
        # Fallback: return raw response in structured format
        return {
            "raw_response": response_text,
            "person_count": None,
            "required_roles_present": {
                "patient": None,
                "doctor": None,
                "interpreter": None
            },
            "unauthorized_persons_detected": None,
            "hipaa_compliance": {
                "compliance_score": None,
                "violations": []
            },
            "interpreter_qa": {
                "professionalism_score": None,
                "issues": []
            }
        }
    
    async def analyze_audio_disturbances(
        self,
        audio_bytes: bytes,
        audio_format: str = "pcm"
    ) -> Dict[str, Any]:
        """
        Analyze audio for third-party disturbances using Gemini.
        
        Note: Gemini doesn't directly support audio, so we'd need to use
        Speech-to-Text API first, then analyze transcript.
        For now, this is a placeholder.
        """
        # TODO: Integrate with Google Speech-to-Text API for audio analysis
        # Then use Gemini to analyze the transcript for disturbances
        
        return {
            "disturbances_detected": False,
            "disturbance_types": [],
            "note": "Audio analysis requires Speech-to-Text integration"
        }
