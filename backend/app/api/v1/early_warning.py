"""
api/v1/early_warning.py

Early-Warning dropout-risk dashboard router (Memora overhaul,
Component 4). Teacher-only, same ownership pattern as analytics.py.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_teacher
from app.database import get_db
from app.models import Teacher
from app.schemas.early_warning import (
    AtRiskStudentEntry,
    AtRiskStudentsResponse,
    EarlyWarningResponse,
)
from app.services.early_warning_service import (
    StudentNotFoundError,
    get_at_risk_students_for_teacher,
    get_early_warning_for_student,
)

router = APIRouter(prefix="/early-warning", tags=["Analytics"])

_STUDENT_NOT_FOUND = HTTPException(
    status_code=status.HTTP_404_NOT_FOUND,
    detail="Student not found.",
)


@router.get("/students/{student_id}", response_model=EarlyWarningResponse)
def get_student_risk_endpoint(
    student_id: int,
    teacher: Teacher = Depends(get_current_teacher),
    db: Session = Depends(get_db),
) -> EarlyWarningResponse:
    """Get the current dropout-risk score for one of the teacher's own students."""
    try:
        result = get_early_warning_for_student(db, teacher.id, student_id)
    except StudentNotFoundError:
        raise _STUDENT_NOT_FOUND

    return EarlyWarningResponse(
        student_id=student_id,
        risk_score=result.risk_score,
        risk_level=result.risk_level,
        contributing_factors=result.contributing_factors,
    )


@router.get("/at-risk", response_model=AtRiskStudentsResponse)
def get_at_risk_students_endpoint(
    risk_threshold: float = 50.0,
    teacher: Teacher = Depends(get_current_teacher),
    db: Session = Depends(get_db),
) -> AtRiskStudentsResponse:
    """List all of the teacher's students at or above the given risk threshold, highest-risk first."""
    entries = get_at_risk_students_for_teacher(db, teacher.id, risk_threshold)
    return AtRiskStudentsResponse(students=[AtRiskStudentEntry(**e) for e in entries])
