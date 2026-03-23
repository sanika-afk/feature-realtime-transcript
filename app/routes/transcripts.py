"""
Transcript and flag management routes.
Handles transcript retrieval, flag validation, and session feedback.
"""
from fastapi import APIRouter, HTTPException, status
from typing import Dict, List, Optional
import uuid
from datetime import datetime

from app.models.transcript import (
    TranscriptSegment,
    AIFlag,
    ReviewerAction,
    SessionFeedback,
    FlagValidationRequest,
    FlagEditRequest,
    FlagCommentRequest,
    SessionFeedbackRequest,
    TranscriptResponse,
    FlagListResponse,
)

router = APIRouter(prefix="/api/transcripts", tags=["transcripts"])

# In-memory storage (replace with database in production)
_transcripts: Dict[str, List[TranscriptSegment]] = {}
_flags: Dict[str, AIFlag] = {}
_reviewer_actions: Dict[str, List[ReviewerAction]] = {}
_session_feedback: Dict[str, SessionFeedback] = {}


@router.get("/{session_id}", response_model=TranscriptResponse)
async def get_transcript(session_id: str):
    """
    Get transcript segments and AI flags for a session.
    
    Args:
        session_id: Session identifier
        
    Returns:
        Transcript segments with associated AI flags
    """
    if session_id not in _transcripts:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Transcript not found for session {session_id}"
        )
    
    segments = _transcripts[session_id]
    
    # Get all flags for this session's segments
    segment_ids = {seg.id for seg in segments}
    session_flags = [
        flag for flag in _flags.values()
        if flag.segment_id in segment_ids
    ]
    
    return TranscriptResponse(
        session_id=session_id,
        segments=segments,
        flags=session_flags
    )


@router.get("/{session_id}/flags", response_model=FlagListResponse)
async def get_session_flags(
    session_id: str,
    severity: Optional[str] = None,
    status_filter: Optional[str] = None,
    error_type: Optional[str] = None
):
    """
    Get all AI flags for a session with optional filtering.
    
    Args:
        session_id: Session identifier
        severity: Filter by severity (critical, major, minor)
        status_filter: Filter by status (pending, confirmed, rejected)
        error_type: Filter by error type
        
    Returns:
        List of AI flags
    """
    if session_id not in _transcripts:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session not found: {session_id}"
        )
    
    segments = _transcripts[session_id]
    segment_ids = {seg.id for seg in segments}
    
    # Get all flags for this session
    session_flags = [
        flag for flag in _flags.values()
        if flag.segment_id in segment_ids
    ]
    
    # Apply filters
    if severity:
        session_flags = [f for f in session_flags if f.severity == severity]
    if status_filter:
        session_flags = [f for f in session_flags if f.status == status_filter]
    if error_type:
        session_flags = [f for f in session_flags if f.error_type == error_type]
    
    return FlagListResponse(
        session_id=session_id,
        flags=session_flags,
        total=len(session_flags)
    )


@router.post("/flags/{flag_id}/validate")
async def validate_flag(flag_id: str, request: FlagValidationRequest):
    """
    Confirm or reject an AI flag.
    
    Args:
        flag_id: Flag identifier
        request: Validation request with action and optional comment
        
    Returns:
        Updated flag
    """
    if flag_id not in _flags:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Flag not found: {flag_id}"
        )
    
    flag = _flags[flag_id]
    
    # Update flag status
    if request.action == "confirm":
        flag.status = "confirmed"
    elif request.action == "reject":
        flag.status = "rejected"
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid action: {request.action}. Must be 'confirm' or 'reject'"
        )
    
    # Create reviewer action
    action = ReviewerAction(
        id=str(uuid.uuid4()),
        flag_id=flag_id,
        reviewer_id="default_reviewer",  # TODO: Get from auth
        action=request.action,
        comment=request.comment
    )
    
    if flag_id not in _reviewer_actions:
        _reviewer_actions[flag_id] = []
    _reviewer_actions[flag_id].append(action)
    
    return {
        "flag_id": flag_id,
        "status": flag.status,
        "action": action.dict()
    }


@router.put("/flags/{flag_id}")
async def edit_flag(flag_id: str, request: FlagEditRequest):
    """
    Edit an AI flag (severity, error type).
    
    Args:
        flag_id: Flag identifier
        request: Edit request with updated fields
        
    Returns:
        Updated flag
    """
    if flag_id not in _flags:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Flag not found: {flag_id}"
        )
    
    flag = _flags[flag_id]
    
    # Create reviewer action for edit
    action = ReviewerAction(
        id=str(uuid.uuid4()),
        flag_id=flag_id,
        reviewer_id="default_reviewer",  # TODO: Get from auth
        action="edit",
        comment=request.comment,
        severity_override=request.severity,
        error_type_override=request.error_type
    )
    
    # Update flag
    if request.severity:
        flag.severity = request.severity
    if request.error_type:
        flag.error_type = request.error_type
    
    if flag_id not in _reviewer_actions:
        _reviewer_actions[flag_id] = []
    _reviewer_actions[flag_id].append(action)
    
    return {
        "flag_id": flag_id,
        "flag": flag.dict(),
        "action": action.dict()
    }


@router.post("/flags/{flag_id}/comment")
async def add_flag_comment(flag_id: str, request: FlagCommentRequest):
    """
    Add a comment to a flag.
    
    Args:
        flag_id: Flag identifier
        request: Comment request
        
    Returns:
        Created reviewer action
    """
    if flag_id not in _flags:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Flag not found: {flag_id}"
        )
    
    action = ReviewerAction(
        id=str(uuid.uuid4()),
        flag_id=flag_id,
        reviewer_id="default_reviewer",  # TODO: Get from auth
        action="comment",
        comment=request.comment
    )
    
    if flag_id not in _reviewer_actions:
        _reviewer_actions[flag_id] = []
    _reviewer_actions[flag_id].append(action)
    
    return action.dict()


@router.post("/{session_id}/feedback")
async def submit_session_feedback(session_id: str, request: SessionFeedbackRequest):
    """
    Submit overall feedback for a session.
    
    Args:
        session_id: Session identifier
        request: Feedback request
        
    Returns:
        Created feedback
    """
    if session_id not in _transcripts:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session not found: {session_id}"
        )
    
    feedback = SessionFeedback(
        id=str(uuid.uuid4()),
        session_id=session_id,
        reviewer_id="default_reviewer",  # TODO: Get from auth
        overall_notes=request.overall_notes,
        tags=request.tags,
        interpreter_rating=request.interpreter_rating,
        recommend_coaching=request.recommend_coaching
    )
    
    _session_feedback[session_id] = feedback
    
    return feedback.dict()


@router.post("/session-feedback")
async def submit_session_feedback_default(request: SessionFeedbackRequest):
    """
    Submit overall feedback for a session (with default session ID).
    
    Args:
        request: Feedback request
        
    Returns:
        Created feedback
    """
    session_id = "default_session"
    
    feedback = SessionFeedback(
        id=str(uuid.uuid4()),
        session_id=session_id,
        reviewer_id="default_reviewer",  # TODO: Get from auth
        overall_notes=request.overall_notes,
        tags=request.tags,
        interpreter_rating=request.interpreter_rating,
        recommend_coaching=request.recommend_coaching
    )
    
    _session_feedback[session_id] = feedback
    
    return feedback.dict()


@router.get("/{session_id}/feedback")
async def get_session_feedback(session_id: str):
    """
    Get feedback for a session.
    
    Args:
        session_id: Session identifier
        
    Returns:
        Session feedback if exists
    """
    if session_id not in _session_feedback:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No feedback found for session {session_id}"
        )
    
    return _session_feedback[session_id].dict()


# Helper function to add transcript data (for testing)
@router.post("/{session_id}/segments")
async def add_transcript_segments(session_id: str, segments: List[TranscriptSegment]):
    """Add transcript segments to a session (for testing/demo)."""
    _transcripts[session_id] = segments
    return {"session_id": session_id, "segments_added": len(segments)}


# Helper function to add flags (for testing)
@router.post("/flags")
async def add_flag(flag: AIFlag):
    """Add an AI flag (for testing/demo)."""
    _flags[flag.id] = flag
    return flag.dict()
