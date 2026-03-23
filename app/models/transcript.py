"""
Data models for the transcript review system.
"""
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field


class TranscriptSegment(BaseModel):
    """A single segment of the transcript with timestamp and speaker."""
    id: str
    session_id: str
    timestamp: float  # seconds from start
    speaker: str  # "Doctor", "Patient", "Interpreter→Patient", "Interpreter→Doctor"
    text: str
    language: str = "en"  # "en", "es", etc.
    created_at: datetime = Field(default_factory=datetime.utcnow)


class AIFlag(BaseModel):
    """AI-generated compliance flag for a transcript segment."""
    id: str
    segment_id: str
    error_type: str  # "omission", "mistranslation", "addition", "noise"
    severity: str  # "critical", "major", "minor"
    confidence: float  # 0.0 to 1.0
    reasoning: str
    original_text: str
    interpreted_text: str
    category: str  # "medical_dosage", "safety", "consent", "general"
    status: str = "pending"  # "pending", "confirmed", "rejected"
    created_at: datetime = Field(default_factory=datetime.utcnow)


class ReviewerAction(BaseModel):
    """Action taken by a reviewer on an AI flag."""
    id: str
    flag_id: str
    reviewer_id: str
    action: str  # "confirm", "reject", "edit"
    comment: Optional[str] = None
    severity_override: Optional[str] = None
    error_type_override: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)


class SessionFeedback(BaseModel):
    """Overall feedback for a session."""
    id: str
    session_id: str
    reviewer_id: str
    overall_notes: str
    tags: List[str] = []  # ["#ProfessionalismIssue", "#BackgroundNoise"]
    interpreter_rating: int = Field(ge=1, le=5)  # 1-5 stars
    recommend_coaching: bool = False
    created_at: datetime = Field(default_factory=datetime.utcnow)


# Request/Response models for API endpoints

class FlagValidationRequest(BaseModel):
    """Request to validate an AI flag."""
    action: str  # "confirm" or "reject"
    comment: Optional[str] = None


class FlagEditRequest(BaseModel):
    """Request to edit an AI flag."""
    severity: Optional[str] = None
    error_type: Optional[str] = None
    comment: Optional[str] = None


class FlagCommentRequest(BaseModel):
    """Request to add a comment to a flag."""
    comment: str


class SessionFeedbackRequest(BaseModel):
    """Request to submit session feedback."""
    overall_notes: str
    tags: List[str] = []
    interpreter_rating: int = Field(ge=1, le=5)
    recommend_coaching: bool = False


class TranscriptResponse(BaseModel):
    """Response containing transcript segments with flags."""
    session_id: str
    segments: List[TranscriptSegment]
    flags: List[AIFlag]


class FlagListResponse(BaseModel):
    """Response containing list of flags."""
    session_id: str
    flags: List[AIFlag]
    total: int
