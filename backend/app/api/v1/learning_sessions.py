"""
api/v1/learning_sessions.py

Learning Session assignment and lifecycle router (Master Specification
Section 5, 6, 10).

Flat resource at /learning-sessions, consistent with /students (Phase 5),
/learning-plans (Phase 6), and /learning-content (Phase 7 Module 5).
Every endpoint requires an authenticated Teacher (get_current_teacher,
frozen in Phase 4). This router contains no business logic or database
access; it only parses requests, calls
app.services.learning_session_service, translates service-layer
exceptions into HTTP responses, and returns schemas.

HTTP status mapping:
    LearningSessionNotFoundError      -> 404
    LearningPlanNotOwnedByTeacherError -> 404  (no existence leak)
    StudentPlanMismatchError           -> 422  (input validation failure)
    LearningContentNotAvailableError   -> 422  (input validation failure)
    InvalidSessionStateError           -> 409  (state conflict)
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_teacher
from app.database import get_db
from app.models import Teacher
from app.schemas.learning_session import (
    LearningSessionCreate,
    LearningSessionEndRequest,
    LearningSessionResponse,
)
from app.services.learning_session_service import (
    InvalidSessionStateError,
    LearningContentNotAvailableError,
    LearningPlanNotOwnedByTeacherError,
    LearningSessionNotFoundError,
    StudentPlanMismatchError,
    abandon_learning_session,
    complete_learning_session,
    create_learning_session,
    get_learning_session_for_teacher,
    list_learning_sessions_for_teacher,
)

router = APIRouter(prefix="/learning-sessions", tags=["Learning Sessions"])

_SESSION_NOT_FOUND = HTTPException(
    status_code=status.HTTP_404_NOT_FOUND,
    detail="Learning session not found.",
)
_PLAN_NOT_OWNED = HTTPException(
    status_code=status.HTTP_404_NOT_FOUND,
    detail="Learning plan not found.",
)


@router.post(
    "", response_model=LearningSessionResponse, status_code=status.HTTP_201_CREATED
)
def create_learning_session_endpoint(
    payload: LearningSessionCreate,
    teacher: Teacher = Depends(get_current_teacher),
    db: Session = Depends(get_db),
) -> LearningSessionResponse:
    """
    Assign a new learning session: place a student into a specific
    content item within one of the teacher's own plans.
    """
    try:
        session = create_learning_session(db, teacher.id, payload)
    except LearningPlanNotOwnedByTeacherError:
        raise _PLAN_NOT_OWNED
    except StudentPlanMismatchError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        )
    except LearningContentNotAvailableError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        )

    return LearningSessionResponse.model_validate(session)


@router.get("", response_model=list[LearningSessionResponse])
def list_learning_sessions_endpoint(
    learning_plan_id: int | None = None,
    teacher: Teacher = Depends(get_current_teacher),
    db: Session = Depends(get_db),
) -> list[LearningSessionResponse]:
    """
    List all learning sessions owned by the authenticated teacher,
    optionally filtered to a single plan via ?learning_plan_id=.
    """
    try:
        sessions = list_learning_sessions_for_teacher(db, teacher.id, learning_plan_id)
    except LearningPlanNotOwnedByTeacherError:
        raise _PLAN_NOT_OWNED

    return [LearningSessionResponse.model_validate(s) for s in sessions]


@router.get("/{session_id}", response_model=LearningSessionResponse)
def get_learning_session_endpoint(
    session_id: int,
    teacher: Teacher = Depends(get_current_teacher),
    db: Session = Depends(get_db),
) -> LearningSessionResponse:
    """Get a single learning session owned by the authenticated teacher."""
    try:
        session = get_learning_session_for_teacher(db, teacher.id, session_id)
    except LearningSessionNotFoundError:
        raise _SESSION_NOT_FOUND

    return LearningSessionResponse.model_validate(session)


@router.post("/{session_id}/complete", response_model=LearningSessionResponse)
def complete_learning_session_endpoint(
    session_id: int,
    payload: LearningSessionEndRequest,
    teacher: Teacher = Depends(get_current_teacher),
    db: Session = Depends(get_db),
) -> LearningSessionResponse:
    """
    Mark a session as completed. Returns 409 if the session is not
    currently in the 'started' state.
    """
    try:
        session = complete_learning_session(db, teacher.id, session_id, payload)
    except LearningSessionNotFoundError:
        raise _SESSION_NOT_FOUND
    except InvalidSessionStateError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        )

    return LearningSessionResponse.model_validate(session)


@router.post("/{session_id}/abandon", response_model=LearningSessionResponse)
def abandon_learning_session_endpoint(
    session_id: int,
    payload: LearningSessionEndRequest,
    teacher: Teacher = Depends(get_current_teacher),
    db: Session = Depends(get_db),
) -> LearningSessionResponse:
    """
    Mark a session as abandoned. Returns 409 if the session is not
    currently in the 'started' state.
    """
    try:
        session = abandon_learning_session(db, teacher.id, session_id, payload)
    except LearningSessionNotFoundError:
        raise _SESSION_NOT_FOUND
    except InvalidSessionStateError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        )

    return LearningSessionResponse.model_validate(session)
