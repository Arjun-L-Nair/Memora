"""
api/v1/learning_content.py

Learning Content management router (Master Specification Section 6, 10).

Flat resource, consistent with /students (Phase 5) and /learning-plans
(Phase 6): the parent learning_plan_id is supplied in the request body
on create, and as an optional query parameter for filtering the list
endpoint — never as a URL path segment. Every endpoint requires an
authenticated Teacher (get_current_teacher, frozen in Phase 4). This
router contains no business logic or database access itself; it only
parses requests, calls app.services.learning_content_service, translates
service-layer exceptions into HTTP responses, and returns schemas.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_teacher
from app.database import get_db
from app.models import Teacher
from app.schemas.learning_content import (
    LearningContentCreate,
    LearningContentResponse,
    LearningContentUpdate,
)
from app.services.learning_content_service import (
    LearningContentNotFoundError,
    LearningPlanNotOwnedByTeacherError,
    create_learning_content,
    deactivate_learning_content,
    get_learning_content_for_teacher,
    list_learning_content_for_teacher,
    update_learning_content,
)

router = APIRouter(prefix="/learning-content", tags=["Learning Content"])

_CONTENT_NOT_FOUND = HTTPException(
    status_code=status.HTTP_404_NOT_FOUND,
    detail="Learning content not found.",
)

# Same status/reasoning as _CONTENT_NOT_FOUND: a teacher should not be
# able to distinguish "that plan doesn't exist" from "that plan belongs
# to another teacher".
_PLAN_NOT_OWNED = HTTPException(
    status_code=status.HTTP_404_NOT_FOUND,
    detail="Learning plan not found.",
)


@router.post(
    "", response_model=LearningContentResponse, status_code=status.HTTP_201_CREATED
)
def create_learning_content_endpoint(
    payload: LearningContentCreate,
    teacher: Teacher = Depends(get_current_teacher),
    db: Session = Depends(get_db),
) -> LearningContentResponse:
    """Create new learning content under one of the authenticated teacher's own plans."""
    try:
        content = create_learning_content(db, teacher.id, payload)
    except LearningPlanNotOwnedByTeacherError:
        raise _PLAN_NOT_OWNED

    return LearningContentResponse.model_validate(content)


@router.get("", response_model=list[LearningContentResponse])
def list_learning_content_endpoint(
    learning_plan_id: int | None = None,
    teacher: Teacher = Depends(get_current_teacher),
    db: Session = Depends(get_db),
) -> list[LearningContentResponse]:
    """
    List all learning content owned by the authenticated teacher,
    optionally filtered to a single plan via ?learning_plan_id=.
    """
    try:
        content = list_learning_content_for_teacher(db, teacher.id, learning_plan_id)
    except LearningPlanNotOwnedByTeacherError:
        raise _PLAN_NOT_OWNED

    return [LearningContentResponse.model_validate(c) for c in content]


@router.get("/{content_id}", response_model=LearningContentResponse)
def get_learning_content_endpoint(
    content_id: int,
    teacher: Teacher = Depends(get_current_teacher),
    db: Session = Depends(get_db),
) -> LearningContentResponse:
    """Get a single piece of learning content owned by the authenticated teacher."""
    try:
        content = get_learning_content_for_teacher(db, teacher.id, content_id)
    except LearningContentNotFoundError:
        raise _CONTENT_NOT_FOUND

    return LearningContentResponse.model_validate(content)


@router.patch("/{content_id}", response_model=LearningContentResponse)
def update_learning_content_endpoint(
    content_id: int,
    payload: LearningContentUpdate,
    teacher: Teacher = Depends(get_current_teacher),
    db: Session = Depends(get_db),
) -> LearningContentResponse:
    """Update learning content's editable fields."""
    try:
        content = update_learning_content(db, teacher.id, content_id, payload)
    except LearningContentNotFoundError:
        raise _CONTENT_NOT_FOUND

    return LearningContentResponse.model_validate(content)


@router.post("/{content_id}/deactivate", response_model=LearningContentResponse)
def deactivate_learning_content_endpoint(
    content_id: int,
    teacher: Teacher = Depends(get_current_teacher),
    db: Session = Depends(get_db),
) -> LearningContentResponse:
    """Deactivate learning content (soft delete; existing sessions are preserved)."""
    try:
        content = deactivate_learning_content(db, teacher.id, content_id)
    except LearningContentNotFoundError:
        raise _CONTENT_NOT_FOUND

    return LearningContentResponse.model_validate(content)
