"""
api/v1/sensory_profile.py

SensoryProfile router (Memora overhaul, Component 3). Student-only,
same auth pattern as learning_companion.py — the authenticated
student's own id is the only identity used, no request parameter ever
supplies a student id.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_student
from app.database import get_db
from app.models import Student
from app.schemas.sensory_profile import SensoryProfileResponse, SensoryProfileUpdateRequest
from app.services.sensory_profile_service import (
    StudentNotFoundError,
    get_or_create_sensory_profile,
    update_sensory_profile,
)

router = APIRouter(prefix="/sensory-profile", tags=["Learning Sessions"])

_STUDENT_NOT_FOUND = HTTPException(
    status_code=status.HTTP_404_NOT_FOUND,
    detail="Student not found.",
)


@router.get("", response_model=SensoryProfileResponse)
def get_sensory_profile_endpoint(
    student: Student = Depends(get_current_student),
    db: Session = Depends(get_db),
) -> SensoryProfileResponse:
    """Get the authenticated student's sensory profile, creating one with defaults if needed."""
    try:
        profile = get_or_create_sensory_profile(db, student.id)
    except StudentNotFoundError:
        raise _STUDENT_NOT_FOUND
    return SensoryProfileResponse.model_validate(profile)


@router.put("", response_model=SensoryProfileResponse)
def update_sensory_profile_endpoint(
    payload: SensoryProfileUpdateRequest,
    student: Student = Depends(get_current_student),
    db: Session = Depends(get_db),
) -> SensoryProfileResponse:
    """Partially update the authenticated student's sensory profile."""
    try:
        profile = update_sensory_profile(db, student.id, **payload.model_dump(exclude_unset=True))
    except StudentNotFoundError:
        raise _STUDENT_NOT_FOUND
    return SensoryProfileResponse.model_validate(profile)
