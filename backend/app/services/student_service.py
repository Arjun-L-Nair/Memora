"""
services/student_service.py

Business logic for teacher-managed Student accounts (Master
Specification Section 4, 6: Student Management).

Every operation here is scoped to the requesting teacher's own students.
A teacher attempting to read/update/deactivate a student belonging to a
different teacher receives the same StudentNotFoundError as if the
student did not exist at all — this avoids leaking which student codes
exist under other teachers' accounts.

Deletion is never performed. Per the frozen soft-delete philosophy
(Phase 2/3 design decisions), removing a student means deactivating it
(is_active=False) — educational history tied to the student must persist.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.security import hash_pin
from app.models import Student
from app.schemas.student import StudentCreate, StudentUpdate


class StudentNotFoundError(Exception):
    """Raised when a student does not exist, or does not belong to the requesting teacher."""


class StudentCodeAlreadyExistsError(Exception):
    """Raised when the requested student_code is already taken (unique constraint)."""


def _is_student_code_conflict(exc: IntegrityError) -> bool:
    """
    Determine whether an IntegrityError is specifically a student_code
    uniqueness violation, as opposed to some other integrity failure
    (e.g. a foreign key violation on teacher_id). Without this check,
    every IntegrityError would be mislabeled as a duplicate student_code,
    which would be misleading for any other constraint failure.
    """
    return "student_code" in str(exc.orig).lower()


def create_student(db: Session, teacher_id: int, payload: StudentCreate) -> Student:
    """
    Create a new student owned by the given teacher.

    Raises StudentCodeAlreadyExistsError if student_code is already
    taken. Any other integrity failure is re-raised unchanged, rather
    than being mislabeled as a duplicate student_code.
    """
    student = Student(
        student_code=payload.student_code,
        full_name=payload.full_name,
        pin_hash=hash_pin(payload.pin),
        teacher_id=teacher_id,
    )
    db.add(student)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        # rollback() already removes a never-committed new object from
        # the session automatically; this guard just makes the cleanup
        # explicit and safe regardless of SQLAlchemy version behavior.
        if student in db:
            db.expunge(student)
        if _is_student_code_conflict(exc):
            raise StudentCodeAlreadyExistsError(
                f"student_code '{payload.student_code}' is already in use."
            ) from exc
        raise

    db.refresh(student)
    return student


def list_students_for_teacher(db: Session, teacher_id: int) -> list[Student]:
    """List all students owned by the given teacher (active and inactive)."""
    result = db.execute(select(Student).where(Student.teacher_id == teacher_id))
    return list(result.scalars().all())


def get_student_for_teacher(db: Session, teacher_id: int, student_id: int) -> Student:
    """
    Get a single student by id, scoped to the requesting teacher.

    Raises StudentNotFoundError if the student does not exist or is
    owned by a different teacher.
    """
    student = db.execute(
        select(Student).where(
            Student.id == student_id, Student.teacher_id == teacher_id
        )
    ).scalar_one_or_none()

    if student is None:
        raise StudentNotFoundError(f"Student {student_id} not found.")

    return student


def update_student(
    db: Session, teacher_id: int, student_id: int, payload: StudentUpdate
) -> Student:
    """
    Update a student's editable profile fields (full_name, student_code).

    Raises StudentNotFoundError if the student does not exist or is
    owned by a different teacher. Raises StudentCodeAlreadyExistsError
    if student_code is being changed to one already in use.
    """
    student = get_student_for_teacher(db, teacher_id, student_id)

    if payload.full_name is not None:
        student.full_name = payload.full_name
    if payload.student_code is not None:
        student.student_code = payload.student_code

    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        if _is_student_code_conflict(exc):
            raise StudentCodeAlreadyExistsError(
                f"student_code '{payload.student_code}' is already in use."
            ) from exc
        raise

    db.refresh(student)
    return student


def deactivate_student(db: Session, teacher_id: int, student_id: int) -> Student:
    """
    Deactivate a student (soft delete). Educational history tied to this
    student is preserved — only is_active is set to False.

    Raises StudentNotFoundError if the student does not exist or is
    owned by a different teacher.
    """
    student = get_student_for_teacher(db, teacher_id, student_id)
    student.is_active = False
    db.commit()
    db.refresh(student)
    return student


def reset_student_pin(
    db: Session, teacher_id: int, student_id: int, new_pin: str
) -> Student:
    """
    Reset a student's PIN. A distinct action from general profile
    updates, since it directly affects the student's ability to log in.

    Raises StudentNotFoundError if the student does not exist or is
    owned by a different teacher.
    """
    student = get_student_for_teacher(db, teacher_id, student_id)
    student.pin_hash = hash_pin(new_pin)
    db.commit()
    db.refresh(student)
    return student
