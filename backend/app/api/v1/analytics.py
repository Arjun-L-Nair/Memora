"""
api/v1/analytics.py

Analytics Dashboard router (Master Specification Section 6, 10, 16).

Teacher-only (get_current_teacher, frozen Phase 4), matching the
ownership pattern used throughout Students/Plans/Content/Sessions.
This router contains no business logic or database access; it only
parses requests, calls app.services.analytics_service, translates
service-layer exceptions into HTTP responses, and returns schemas.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_teacher
from app.database import get_db
from app.models import Teacher
from app.schemas.analytics import StudentAnalyticsResponse
from app.services.analytics_service import StudentNotFoundError, get_student_analytics

router = APIRouter(prefix="/analytics", tags=["Analytics"])

_STUDENT_NOT_FOUND = HTTPException(
    status_code=status.HTTP_404_NOT_FOUND,
    detail="Student not found.",
)


@router.get("/students/{student_id}", response_model=StudentAnalyticsResponse)
def get_student_analytics_endpoint(
    student_id: int,
    teacher: Teacher = Depends(get_current_teacher),
    db: Session = Depends(get_db),
) -> StudentAnalyticsResponse:
    """Get an aggregated progress summary for one of the teacher's own students."""
    try:
        return get_student_analytics(db, teacher.id, student_id)
    except StudentNotFoundError:
        raise _STUDENT_NOT_FOUND
