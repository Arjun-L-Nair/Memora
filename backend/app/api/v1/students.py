"""
api/v1/students.py

Student management router (Master Specification Section 4, 6).

Every endpoint requires an authenticated Teacher (get_current_teacher,
frozen in Phase 4) — students never manage their own accounts. This
router contains no business logic or database access itself; it only
parses requests, calls app.services.student_service, translates
service-layer exceptions into HTTP responses, and returns schemas.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_teacher
from app.database import get_db
from app.models import Teacher
from app.schemas.student import (
    StudentCreate,
    StudentPinResetRequest,
    StudentResponse,
    StudentUpdate,
)
from app.services.student_service import (
    StudentCodeAlreadyExistsError,
    StudentNotFoundError,
    create_student,
    deactivate_student,
    get_student_for_teacher,
    list_students_for_teacher,
    reset_student_pin,
    update_student,
)

router = APIRouter(prefix="/students", tags=["Students"])

_STUDENT_NOT_FOUND = HTTPException(
    status_code=status.HTTP_404_NOT_FOUND,
    detail="Student not found.",
)


def _student_code_conflict(payload_code: str | None) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail=f"student_code '{payload_code}' is already in use.",
    )


@router.post("", response_model=StudentResponse, status_code=status.HTTP_201_CREATED)
def create_student_endpoint(
    payload: StudentCreate,
    teacher: Teacher = Depends(get_current_teacher),
    db: Session = Depends(get_db),
) -> StudentResponse:
    """Create a new student owned by the authenticated teacher."""
    try:
        student = create_student(db, teacher.id, payload)
    except StudentCodeAlreadyExistsError:
        raise _student_code_conflict(payload.student_code)

    return StudentResponse.model_validate(student)


@router.get("", response_model=list[StudentResponse])
def list_students_endpoint(
    teacher: Teacher = Depends(get_current_teacher),
    db: Session = Depends(get_db),
) -> list[StudentResponse]:
    """List all students owned by the authenticated teacher."""
    students = list_students_for_teacher(db, teacher.id)
    return [StudentResponse.model_validate(s) for s in students]


@router.get("/{student_id}", response_model=StudentResponse)
def get_student_endpoint(
    student_id: int,
    teacher: Teacher = Depends(get_current_teacher),
    db: Session = Depends(get_db),
) -> StudentResponse:
    """Get a single student owned by the authenticated teacher."""
    try:
        student = get_student_for_teacher(db, teacher.id, student_id)
    except StudentNotFoundError:
        raise _STUDENT_NOT_FOUND

    return StudentResponse.model_validate(student)


@router.patch("/{student_id}", response_model=StudentResponse)
def update_student_endpoint(
    student_id: int,
    payload: StudentUpdate,
    teacher: Teacher = Depends(get_current_teacher),
    db: Session = Depends(get_db),
) -> StudentResponse:
    """Update a student's profile fields (full_name, student_code)."""
    try:
        student = update_student(db, teacher.id, student_id, payload)
    except StudentNotFoundError:
        raise _STUDENT_NOT_FOUND
    except StudentCodeAlreadyExistsError:
        raise _student_code_conflict(payload.student_code)

    return StudentResponse.model_validate(student)


@router.post("/{student_id}/deactivate", response_model=StudentResponse)
def deactivate_student_endpoint(
    student_id: int,
    teacher: Teacher = Depends(get_current_teacher),
    db: Session = Depends(get_db),
) -> StudentResponse:
    """Deactivate a student (soft delete; educational history is preserved)."""
    try:
        student = deactivate_student(db, teacher.id, student_id)
    except StudentNotFoundError:
        raise _STUDENT_NOT_FOUND

    return StudentResponse.model_validate(student)


@router.post("/{student_id}/reset-pin", response_model=StudentResponse)
def reset_student_pin_endpoint(
    student_id: int,
    payload: StudentPinResetRequest,
    teacher: Teacher = Depends(get_current_teacher),
    db: Session = Depends(get_db),
) -> StudentResponse:
    """Reset a student's 4-digit PIN."""
    try:
        student = reset_student_pin(db, teacher.id, student_id, payload.pin)
    except StudentNotFoundError:
        raise _STUDENT_NOT_FOUND

    return StudentResponse.model_validate(student)
