"""
Models package initialization.
"""
# Bot models (from models.py)
from app.models_legacy import (
    CreateBotRequest,
    BotResponse,
    BotStatusResponse,
)

# Transcript models (from models/transcript.py)
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

__all__ = [
    # Bot models
    "CreateBotRequest",
    "BotResponse",
    "BotStatusResponse",
    # Transcript models
    "TranscriptSegment",
    "AIFlag",
    "ReviewerAction",
    "SessionFeedback",
    "FlagValidationRequest",
    "FlagEditRequest",
    "FlagCommentRequest",
    "SessionFeedbackRequest",
    "TranscriptResponse",
    "FlagListResponse",
]
