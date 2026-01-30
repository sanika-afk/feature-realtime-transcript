"""
HIPAA Compliance Analyzer
Combines results from Video Intelligence API and Gemini for comprehensive analysis.
All analysis logic is handled by AI models via prompts.
"""
import asyncio
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime
from app.video_intelligence_client import VideoIntelligenceStreamingClient
from app.gemini_client import GeminiClient
from google.cloud.videointelligence_v1 import Feature

logger = logging.getLogger(__name__)


class HIPAAComplianceAnalyzer:
    """
    Analyzes medical consultation videos for HIPAA compliance.
    Uses both Video Intelligence API and Gemini for comprehensive analysis.
    """
    
    def __init__(
        self,
        vi_client: VideoIntelligenceStreamingClient,
        gemini_client: GeminiClient
    ):
        """
        Initialize HIPAA compliance analyzer.
        
        Args:
            vi_client: Video Intelligence API client
            gemini_client: Gemini API client
        """
        self.vi_client = vi_client
        self.gemini_client = gemini_client
        self.analysis_history: List[Dict[str, Any]] = []
    
    async def analyze_frame_dual(
        self,
        frame_bytes: bytes,
        audio_transcript: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Analyze a frame using both Video Intelligence API and Gemini.
        Compares speed and combines results.
        
        Args:
            frame_bytes: JPEG frame bytes
            audio_transcript: Optional audio transcript
        
        Returns:
            Combined analysis results with speed comparison
        """
        # Run both analyses concurrently
        vi_task = self._analyze_with_vi(frame_bytes)
        gemini_task = self.gemini_client.analyze_frame(
            frame_bytes,
            audio_transcript,
            self._get_previous_context()
        )
        
        # Wait for both to complete
        vi_result, gemini_result = await asyncio.gather(
            vi_task,
            gemini_task,
            return_exceptions=True
        )
        
        # Handle exceptions
        if isinstance(vi_result, Exception):
            logger.error(f"Video Intelligence API error: {vi_result}")
            vi_result = {"error": str(vi_result), "api": "video_intelligence"}
        
        if isinstance(gemini_result, Exception):
            logger.error(f"Gemini API error: {gemini_result}")
            gemini_result = {"error": str(gemini_result), "api": "gemini"}
        
        # Combine results
        combined = self._combine_results(vi_result, gemini_result)
        
        # Store in history
        self.analysis_history.append(combined)
        
        return combined
    
    async def _analyze_with_vi(self, frame_bytes: bytes) -> Dict[str, Any]:
        """Analyze frame using Video Intelligence API (frame-based)."""
        import time
        start_time = time.time()
        
        # For frame-based analysis, we'd need to use the batch API
        # This is a simplified version - in production, batch frames
        # Note: Video Intelligence API streaming is better for continuous video
        
        # For now, return a placeholder that indicates we'd use object tracking
        # In production, you'd batch frames and use the batch annotate API
        
        return {
            "api": "video_intelligence",
            "processing_time": time.time() - start_time,
            "note": "Frame-based analysis requires batch API or streaming",
            "person_count": None,
            "objects_detected": []
        }
    
    def _combine_results(
        self,
        vi_result: Dict[str, Any],
        gemini_result: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Combine results from both APIs."""
        combined = {
            "timestamp": datetime.utcnow().isoformat(),
            "video_intelligence": vi_result,
            "gemini": gemini_result,
            "speed_comparison": {
                "vi_time": vi_result.get("processing_time", 0),
                "gemini_time": gemini_result.get("processing_time", 0),
                "faster_api": "gemini" if gemini_result.get("processing_time", float('inf')) < vi_result.get("processing_time", float('inf')) else "video_intelligence"
            },
            "combined_analysis": {
                "person_count": gemini_result.get("person_count") or vi_result.get("person_count"),
                "hipaa_compliance": gemini_result.get("hipaa_compliance", {}),
                "interpreter_qa": gemini_result.get("interpreter_qa", {}),
                "unauthorized_persons": gemini_result.get("unauthorized_persons_detected", False),
                "compliance_status": self._determine_compliance_status(gemini_result)
            }
        }
        
        return combined
    
    def _determine_compliance_status(self, gemini_result: Dict[str, Any]) -> str:
        """Determine overall HIPAA compliance status."""
        compliance = gemini_result.get("hipaa_compliance", {})
        score = compliance.get("compliance_score", 0)
        violations = compliance.get("violations", [])
        
        if score >= 90 and not violations:
            return "COMPLIANT"
        elif score >= 70:
            return "MINOR_ISSUES"
        elif score >= 50:
            return "NON_COMPLIANT"
        else:
            return "CRITICAL_VIOLATIONS"
    
    def _get_previous_context(self) -> Optional[Dict[str, Any]]:
        """Get context from previous analyses."""
        if not self.analysis_history:
            return None
        
        # Get last 5 analyses for context
        recent = self.analysis_history[-5:]
        return {
            "recent_analyses": len(recent),
            "last_compliance_status": recent[-1].get("combined_analysis", {}).get("compliance_status") if recent else None,
            "trend": "improving" if len(recent) > 1 and recent[-1].get("combined_analysis", {}).get("hipaa_compliance", {}).get("compliance_score", 0) > recent[-2].get("combined_analysis", {}).get("hipaa_compliance", {}).get("compliance_score", 0) else "stable"
        }
    
    def get_summary(self) -> Dict[str, Any]:
        """Get summary of all analyses."""
        if not self.analysis_history:
            return {"message": "No analyses performed yet"}
        
        total = len(self.analysis_history)
        compliant = sum(1 for a in self.analysis_history if a.get("combined_analysis", {}).get("compliance_status") == "COMPLIANT")
        avg_vi_time = sum(a.get("speed_comparison", {}).get("vi_time", 0) for a in self.analysis_history) / total
        avg_gemini_time = sum(a.get("speed_comparison", {}).get("gemini_time", 0) for a in self.analysis_history) / total
        
        return {
            "total_frames_analyzed": total,
            "compliance_rate": (compliant / total * 100) if total > 0 else 0,
            "average_processing_times": {
                "video_intelligence": avg_vi_time,
                "gemini": avg_gemini_time,
                "faster_on_average": "gemini" if avg_gemini_time < avg_vi_time else "video_intelligence"
            },
            "recent_status": self.analysis_history[-1].get("combined_analysis", {}).get("compliance_status") if self.analysis_history else None
        }
