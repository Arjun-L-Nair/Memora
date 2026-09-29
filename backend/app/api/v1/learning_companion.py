"""
api/v1/learning_companion.py

Mira (student learning companion) router (Memora overhaul, Component 2).

Student-only (get_current_student). This router contains no business
logic - it parses the request, calls
app.services.learning_companion_service, translates service-layer
exceptions into HTTP responses, and returns the schema.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_student
from app.database import get_db
from app.models import Student
from app.schemas.learning_companion import (
    CompanionMessageRequest,
    CompanionMessageResponse,
    ConversationHistoryResponse,
    ConversationTurn,
)
from app.services.learning_companion_service import (
    StudentNotFoundError,
    generate_companion_message,
    get_conversation_history,
)

router = APIRouter(prefix="/learning-companion", tags=["Learning Sessions"])

_STUDENT_NOT_FOUND = HTTPException(
    status_code=status.HTTP_404_NOT_FOUND,
    detail="Student not found.",
)


@router.post("/message", response_model=CompanionMessageResponse)
def get_companion_message_endpoint(
    payload: CompanionMessageRequest,
    student: Student = Depends(get_current_student),
    db: Session = Depends(get_db),
) -> CompanionMessageResponse:
    """
    Get a message from Mira, personalized from the authenticated
    student's own data and prior conversation history.
    """
    try:
        result = generate_companion_message(
            db, student.id, payload.student_message, payload.interaction_mode
        )
    except StudentNotFoundError:
        raise _STUDENT_NOT_FOUND

    # Look up the just-persisted detected emotion for the response
    # (None if no student_message was sent this turn).
    history = get_conversation_history(db, student.id, limit=2)
    detected_emotion = None
    for turn in history:
        if turn.role == "student":
            detected_emotion = turn.emotion_detected

    return CompanionMessageResponse(
        message=result.message,
        generated_by=result.generated_by,
        detected_emotion=detected_emotion,
    )


@router.get("/history", response_model=ConversationHistoryResponse)
def get_companion_history_endpoint(
    student: Student = Depends(get_current_student),
    db: Session = Depends(get_db),
) -> ConversationHistoryResponse:
    """Return the authenticated student's persisted Mira chat history, oldest-first."""
    rows = get_conversation_history(db, student.id, limit=100)
    return ConversationHistoryResponse(
        turns=[ConversationTurn.model_validate(row) for row in rows]
    )
