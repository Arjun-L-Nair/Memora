"""
api/v1/learning_reflection.py

Learning Reflection router (Master Specification Section 5, 6, 7, 10).

Student-triggered, mirroring api/v1/quiz.py's authentication/ownership
pattern exactly (get_current_student, frozen Phase 4) — per the
approved Phase 11 design, Reflection sits within the student's own
session flow, not the teacher-triggered pattern used for Engagement
Prediction/Adaptive Suggestions.

This router contains no business logic or database access; it only
parses requests, calls app.services.learning_reflection_service,
translates service-layer exceptions into HTTP responses, and returns
schemas.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_student
from app.database import get_db
from app.models import Student
from app.schemas.learning_reflection import LearningReflectionResponse
from app.services.learning_reflection_service import (
    LearningReflectionAlreadyExistsError,
    LearningReflectionNotFoundError,
    LearningSessionNotFoundError,
    generate_learning_reflection,
    get_learning_reflection_by_session_for_student,
    get_learning_reflection_for_student,
)

router = APIRouter(prefix="/learning-reflections", tags=["Learning Sessions"])

_SESSION_NOT_FOUND = HTTPException(
    status_code=status.HTTP_404_NOT_FOUND,
    detail="Learning session not found.",
)
_REFLECTION_NOT_FOUND = HTTPException(
    status_code=status.HTTP_404_NOT_FOUND,
    detail="Learning reflection not found.",
)


@router.post(
    "/generate/{learning_session_id}",
    response_model=LearningReflectionResponse,
    status_code=status.HTTP_201_CREATED,
)
def generate_learning_reflection_endpoint(
    learning_session_id: int,
    student: Student = Depends(get_current_student),
    db: Session = Depends(get_db),
) -> LearningReflectionResponse:
    """
    Generate a reflection for one of the student's own sessions. The
    active provider (Ollama first, template fallback) generates the
    text exactly once, at creation time. Returns 409 if a reflection
    already exists for this session.
    """
    try:
        reflection = generate_learning_reflection(db, student.id, learning_session_id)
    except LearningSessionNotFoundError:
        raise _SESSION_NOT_FOUND
    except LearningReflectionAlreadyExistsError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        )

    return LearningReflectionResponse.model_validate(reflection)


@router.get(
    "/by-session/{learning_session_id}",
    response_model=LearningReflectionResponse | None,
)
def get_learning_reflection_by_session_endpoint(
    learning_session_id: int,
    student: Student = Depends(get_current_student),
    db: Session = Depends(get_db),
) -> LearningReflectionResponse | None:
    """
    Look up the reflection (if any) already belonging to one of the
    student's own sessions, without attempting to generate one. Returns
    null when no reflection has been generated yet — lets the frontend
    resume an existing reflection instead of treating a second
    "generate" call's 409 as a dead end.
    """
    try:
        reflection = get_learning_reflection_by_session_for_student(
            db, student.id, learning_session_id
        )
    except LearningSessionNotFoundError:
        raise _SESSION_NOT_FOUND

    return LearningReflectionResponse.model_validate(reflection) if reflection is not None else None


@router.get("/{reflection_id}", response_model=LearningReflectionResponse)
def get_learning_reflection_endpoint(
    reflection_id: int,
    student: Student = Depends(get_current_student),
    db: Session = Depends(get_db),
) -> LearningReflectionResponse:
    """Get a reflection owned by the authenticated student."""
    try:
        reflection = get_learning_reflection_for_student(db, student.id, reflection_id)
    except LearningReflectionNotFoundError:
        raise _REFLECTION_NOT_FOUND

    return LearningReflectionResponse.model_validate(reflection)
