"""
services/admin_student_service.py

Business logic for Admin-level Student oversight (Master Specification
Section 4, 6: Administrator).

Deliberately minimal: read-only, system-wide visibility only. Student
creation, profile updates, and PIN resets remain exclusively a
Teacher's responsibility via their own students (student_service.py,
Phase 5, frozen) — Admin does not bypass or duplicate that ownership
model. This mirrors the spec's own description of Admin overseeing
rather than directly managing day-to-day student operations.

Reuses StudentNotFoundError directly from student_service.py rather
than defining a duplicate exception class.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Student
from app.services.student_service import StudentNotFoundError

__all__ = ["StudentNotFoundError", "list_all_students", "get_student_system_wide"]


def list_all_students(db: Session) -> list[Student]:
    """List all students system-wide (active and inactive, across all teachers)."""
    result = db.execute(select(Student))
    return list(result.scalars().all())


def get_student_system_wide(db: Session, student_id: int) -> Student:
    """
    Get a single student by id, system-wide (no teacher-ownership
    scoping — Admin may view any student).

    Raises StudentNotFoundError if the student does not exist.
    """
    student = db.execute(
        select(Student).where(Student.id == student_id)
    ).scalar_one_or_none()

    if student is None:
        raise StudentNotFoundError(f"Student {student_id} not found.")

    return student
