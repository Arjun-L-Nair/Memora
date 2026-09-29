"""
services/admin_teacher_service.py

Business logic for Admin-controlled Teacher management (Master
Specification Section 4, 6: Administrator).

Mirrors student_service.py's shape (Phase 5) — same IntegrityError
conflict-detection pattern, same exception style — but scoped
system-wide rather than to an owning teacher: Admin oversees ALL
teachers, so there is no ownership filter here, unlike Student's
teacher-scoped queries.

Deletion is never performed. Per the frozen soft-delete philosophy,
removing a teacher means deactivating it (is_active=False) — students
and educational history tied to the teacher must persist. Unlike
Student (Phase 5, deactivate-only), Teacher management here supports
BOTH activate and deactivate, since Admin oversight explicitly
requires the ability to restore a teacher account.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models import Teacher
from app.schemas.admin import TeacherCreateByAdmin


class TeacherNotFoundError(Exception):
    """Raised when a teacher does not exist."""


class TeacherEmailAlreadyExistsError(Exception):
    """Raised when the requested email is already taken (unique constraint)."""


def _is_email_conflict(exc: IntegrityError) -> bool:
    """
    Determine whether an IntegrityError is specifically an email
    uniqueness violation, as opposed to some other integrity failure.
    Mirrors student_service._is_student_code_conflict's reasoning.
    """
    return "email" in str(exc.orig).lower()


def create_teacher(db: Session, payload: TeacherCreateByAdmin) -> Teacher:
    """
    Create a new teacher account. Teachers cannot self-register, so
    Admin sets the initial password directly.

    Raises TeacherEmailAlreadyExistsError if email is already taken.
    """
    teacher = Teacher(
        full_name=payload.full_name,
        email=payload.email,
        password_hash=hash_password(payload.password),
        organization_name=payload.organization_name,
    )
    db.add(teacher)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        if teacher in db:
            db.expunge(teacher)
        if _is_email_conflict(exc):
            raise TeacherEmailAlreadyExistsError(
                f"email '{payload.email}' is already in use."
            ) from exc
        raise

    db.refresh(teacher)
    return teacher


def list_teachers(db: Session) -> list[Teacher]:
    """List all teachers system-wide (active and inactive)."""
    result = db.execute(select(Teacher))
    return list(result.scalars().all())


def get_teacher(db: Session, teacher_id: int) -> Teacher:
    """
    Get a single teacher by id.

    Raises TeacherNotFoundError if the teacher does not exist.
    """
    teacher = db.execute(
        select(Teacher).where(Teacher.id == teacher_id)
    ).scalar_one_or_none()

    if teacher is None:
        raise TeacherNotFoundError(f"Teacher {teacher_id} not found.")

    return teacher


def deactivate_teacher(db: Session, teacher_id: int) -> Teacher:
    """
    Deactivate a teacher (soft delete). Students and educational
    history tied to this teacher are preserved — only is_active is set
    to False.

    Raises TeacherNotFoundError if the teacher does not exist.
    """
    teacher = get_teacher(db, teacher_id)
    teacher.is_active = False
    db.commit()
    db.refresh(teacher)
    return teacher


def activate_teacher(db: Session, teacher_id: int) -> Teacher:
    """
    Reactivate a previously deactivated teacher.

    Raises TeacherNotFoundError if the teacher does not exist.
    """
    teacher = get_teacher(db, teacher_id)
    teacher.is_active = True
    db.commit()
    db.refresh(teacher)
    return teacher
