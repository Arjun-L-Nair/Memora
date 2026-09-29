"""
database/seed_dev_teacher.py

TEMPORARY DEVELOPMENT SEED — to be removed once the lightweight
Administrator module is implemented (Master Specification Section 4/6).

Inserts exactly one default Teacher account for local testing of Phase 4
(Authentication) and Phase 5 (Student Management), since there is
currently no way to create a Teacher account other than direct database
insertion (Teacher CRUD/registration is explicitly out of scope — see
Master Specification Section 4: Administrator manages teachers).

Idempotent: querying by email first, and only inserting if no matching
Teacher exists, means running this any number of times never creates a
duplicate or modifies an existing teacher's data (including its
password hash).

Uses the same SessionLocal, Teacher ORM model, and hash_password()
utility already established in the codebase — no new hashing logic, no
schema change, no change to authentication.
"""

from __future__ import annotations

from sqlalchemy import select

from app.core.security import hash_password
from app.database.session import SessionLocal
from app.models import Teacher

DEV_TEACHER_EMAIL = "teacher@test.com"
DEV_TEACHER_FULL_NAME = "Development Teacher"
DEV_TEACHER_PASSWORD = "password123"


def seed_dev_teacher() -> None:
    """
    Insert one default development Teacher account if it does not
    already exist. Never modifies an existing teacher; never creates
    duplicates.
    """
    db = SessionLocal()
    try:
        existing = db.execute(
            select(Teacher).where(Teacher.email == DEV_TEACHER_EMAIL)
        ).scalar_one_or_none()

        if existing is not None:
            print("Development teacher already exists.")
            return

        teacher = Teacher(
            full_name=DEV_TEACHER_FULL_NAME,
            email=DEV_TEACHER_EMAIL,
            password_hash=hash_password(DEV_TEACHER_PASSWORD),
            is_active=True,
        )
        db.add(teacher)
        db.commit()
        print("Development teacher created successfully.")
    finally:
        db.close()


if __name__ == "__main__":
    # python -m app.database.seed_dev_teacher
    seed_dev_teacher()
