"""
api/v1/student_learning.py

Student learning workflow router (Master Specification Section 5, 6:
Today's Learning, Progress Tracking).

Every endpoint requires an authenticated Student (get_current_student,
frozen Phase 4). This router contains no business logic or database
access; it only parses requests, calls
app.services.student_learning_service, translates service-layer
exceptions into HTTP responses, and returns schemas.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_student
from app.database import get_db
from app.models import Student
from app.schemas.learning_content import LearningContentResponse
from app.schemas.learning_session import LearningSessionEndRequest, LearningSessionResponse
from app.schemas.student_learning import RecommendedContentResponse
from app.services.student_learning_service import (
    InvalidSessionStateError,
    LearningPlanNotFoundForStudentError,
    LearningSessionNotFoundError,
    abandon_session_as_student,
    complete_session_as_student,
    get_all_sessions_for_student,
    get_content_for_session,
    get_recommended_content_for_student,
    get_todays_learning,
)

router = APIRouter(prefix="/student-learning", tags=["Learning Sessions"])

_SESSION_NOT_FOUND = HTTPException(
    status_code=status.HTTP_404_NOT_FOUND,
    detail="Learning session not found.",
)

_PLAN_NOT_FOUND = HTTPException(
    status_code=status.HTTP_404_NOT_FOUND,
    detail="Learning plan not found.",
)


@router.get("/today", response_model=list[LearningSessionResponse])
def get_todays_learning_endpoint(
    student: Student = Depends(get_current_student),
    db: Session = Depends(get_db),
) -> list[LearningSessionResponse]:
    """
    "Today's Learning": the student's currently in-progress sessions,
    most recently started first.
    """
    sessions = get_todays_learning(db, student.id)
    return [LearningSessionResponse.model_validate(s) for s in sessions]


@router.get("/sessions", response_model=list[LearningSessionResponse])
def list_all_sessions_endpoint(
    student: Student = Depends(get_current_student),
    db: Session = Depends(get_db),
) -> list[LearningSessionResponse]:
    """All of the student's sessions, any status (progress history)."""
    sessions = get_all_sessions_for_student(db, student.id)
    return [LearningSessionResponse.model_validate(s) for s in sessions]


@router.get("/sessions/{session_id}/content", response_model=LearningContentResponse)
def get_session_content_endpoint(
    session_id: int,
    student: Student = Depends(get_current_student),
    db: Session = Depends(get_db),
) -> LearningContentResponse:
    """
    The exact learning content tied to one of the student's own
    sessions — not a re-derived recommendation. Use this when a
    session already exists and its assigned content needs to be
    displayed (e.g. the student's Learning page); use
    /plans/{id}/recommended-content only when proposing what content a
    *new* session should use.
    """
    try:
        content = get_content_for_session(db, student.id, session_id)
    except LearningSessionNotFoundError:
        raise _SESSION_NOT_FOUND

    return LearningContentResponse.model_validate(content)


@router.post("/sessions/{session_id}/complete", response_model=LearningSessionResponse)
def complete_session_endpoint(
    session_id: int,
    payload: LearningSessionEndRequest,
    student: Student = Depends(get_current_student),
    db: Session = Depends(get_db),
) -> LearningSessionResponse:
    """Mark one of the student's own sessions as completed."""
    try:
        session = complete_session_as_student(db, student.id, session_id, payload)
    except LearningSessionNotFoundError:
        raise _SESSION_NOT_FOUND
    except InvalidSessionStateError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        )

    return LearningSessionResponse.model_validate(session)


@router.post("/sessions/{session_id}/abandon", response_model=LearningSessionResponse)
def abandon_session_endpoint(
    session_id: int,
    payload: LearningSessionEndRequest,
    student: Student = Depends(get_current_student),
    db: Session = Depends(get_db),
) -> LearningSessionResponse:
    """Mark one of the student's own sessions as abandoned."""
    try:
        session = abandon_session_as_student(db, student.id, session_id, payload)
    except LearningSessionNotFoundError:
        raise _SESSION_NOT_FOUND
    except InvalidSessionStateError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        )

    return LearningSessionResponse.model_validate(session)


@router.get(
    "/plans/{learning_plan_id}/recommended-content",
    response_model=RecommendedContentResponse,
)
def get_recommended_content_endpoint(
    learning_plan_id: int,
    student: Student = Depends(get_current_student),
    db: Session = Depends(get_db),
) -> RecommendedContentResponse:
    """
    Difficulty-aware content recommendation for one of the
    authenticated student's own learning plans (Phase 15 Module 4).

    The student identity is always taken from get_current_student —
    never from the request — so a student can only ever receive
    recommendations scoped to their own plans, which in turn belong to
    exactly one teacher. `content` is null when the plan currently has
    no active content to recommend; this is a normal, expected
    response, not an error.

    Never creates a LearningSession — this endpoint only recommends;
    starting a session remains a separate, explicit action via the
    existing teacher-driven session-creation flow.
    """
    try:
        result = get_recommended_content_for_student(db, student.id, learning_plan_id)
    except LearningPlanNotFoundForStudentError:
        raise _PLAN_NOT_FOUND

    return RecommendedContentResponse(
        learning_plan_id=learning_plan_id,
        content=(
            LearningContentResponse.model_validate(result.content)
            if result.content is not None
            else None
        ),
        reasoning=result.reasoning,
    )
