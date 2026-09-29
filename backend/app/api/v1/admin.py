"""
api/v1/admin.py

Admin router (Master Specification Section 4, 6, 16: Administrator).

POST /admin/login is the only unauthenticated endpoint; every other
endpoint requires get_current_admin (frozen extension, Module 2). This
router contains no business logic or database access itself; it only
parses requests, calls the appropriate admin_*_service module,
translates service-layer exceptions into HTTP responses, and returns
schemas.

Student administrative listing reuses schemas.student.StudentResponse
directly (see schemas/admin.py's module docstring) — no duplicate
schema.
"""

from __future__ import annotations

import subprocess
import sys

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import get_current_admin
from app.database import get_db
from app.models import Admin
from app.schemas.admin import (
    AdminLoginRequest,
    SystemStatisticsResponse,
    TeacherAdminResponse,
    TeacherCreateByAdmin,
)
from app.schemas.auth import TokenResponse
from app.schemas.student import StudentResponse
from app.services.admin_auth_service import AuthenticationError, authenticate_admin
from app.services.admin_stats_service import get_system_statistics
from app.services.admin_student_service import (
    StudentNotFoundError,
    get_student_system_wide,
    list_all_students,
)
from app.services.admin_teacher_service import (
    TeacherEmailAlreadyExistsError,
    TeacherNotFoundError,
    activate_teacher,
    create_teacher,
    deactivate_teacher,
    get_teacher,
    list_teachers,
)
from app.services.auth_service import issue_token_pair

router = APIRouter(prefix="/admin", tags=["Admin"])

_INVALID_CREDENTIALS = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Invalid credentials.",
)
_TEACHER_NOT_FOUND = HTTPException(
    status_code=status.HTTP_404_NOT_FOUND,
    detail="Teacher not found.",
)
_STUDENT_NOT_FOUND = HTTPException(
    status_code=status.HTTP_404_NOT_FOUND,
    detail="Student not found.",
)


@router.post("/login", response_model=TokenResponse)
def admin_login(
    payload: AdminLoginRequest,
    db: Session = Depends(get_db),
) -> TokenResponse:
    """Authenticate an admin by email + password and issue tokens."""
    try:
        admin = authenticate_admin(db, payload.email, payload.password)
    except AuthenticationError:
        raise _INVALID_CREDENTIALS

    access_token, refresh_token = issue_token_pair(subject=str(admin.id), role="admin")
    return TokenResponse(access_token=access_token, refresh_token=refresh_token)


@router.post(
    "/teachers", response_model=TeacherAdminResponse, status_code=status.HTTP_201_CREATED
)
def create_teacher_endpoint(
    payload: TeacherCreateByAdmin,
    admin: Admin = Depends(get_current_admin),
    db: Session = Depends(get_db),
) -> TeacherAdminResponse:
    """Create a new teacher account."""
    try:
        teacher = create_teacher(db, payload)
    except TeacherEmailAlreadyExistsError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        )

    return TeacherAdminResponse.model_validate(teacher)


@router.get("/teachers", response_model=list[TeacherAdminResponse])
def list_teachers_endpoint(
    admin: Admin = Depends(get_current_admin),
    db: Session = Depends(get_db),
) -> list[TeacherAdminResponse]:
    """List all teachers system-wide."""
    teachers = list_teachers(db)
    return [TeacherAdminResponse.model_validate(t) for t in teachers]


@router.get("/teachers/{teacher_id}", response_model=TeacherAdminResponse)
def get_teacher_endpoint(
    teacher_id: int,
    admin: Admin = Depends(get_current_admin),
    db: Session = Depends(get_db),
) -> TeacherAdminResponse:
    """Get a single teacher by id."""
    try:
        teacher = get_teacher(db, teacher_id)
    except TeacherNotFoundError:
        raise _TEACHER_NOT_FOUND

    return TeacherAdminResponse.model_validate(teacher)


@router.post("/teachers/{teacher_id}/deactivate", response_model=TeacherAdminResponse)
def deactivate_teacher_endpoint(
    teacher_id: int,
    admin: Admin = Depends(get_current_admin),
    db: Session = Depends(get_db),
) -> TeacherAdminResponse:
    """Deactivate a teacher (soft delete; students/history are preserved)."""
    try:
        teacher = deactivate_teacher(db, teacher_id)
    except TeacherNotFoundError:
        raise _TEACHER_NOT_FOUND

    return TeacherAdminResponse.model_validate(teacher)


@router.post("/teachers/{teacher_id}/activate", response_model=TeacherAdminResponse)
def activate_teacher_endpoint(
    teacher_id: int,
    admin: Admin = Depends(get_current_admin),
    db: Session = Depends(get_db),
) -> TeacherAdminResponse:
    """Reactivate a previously deactivated teacher."""
    try:
        teacher = activate_teacher(db, teacher_id)
    except TeacherNotFoundError:
        raise _TEACHER_NOT_FOUND

    return TeacherAdminResponse.model_validate(teacher)


@router.get("/students", response_model=list[StudentResponse])
def list_all_students_endpoint(
    admin: Admin = Depends(get_current_admin),
    db: Session = Depends(get_db),
) -> list[StudentResponse]:
    """List all students system-wide, across all teachers."""
    students = list_all_students(db)
    return [StudentResponse.model_validate(s) for s in students]


@router.get("/students/{student_id}", response_model=StudentResponse)
def get_student_endpoint(
    student_id: int,
    admin: Admin = Depends(get_current_admin),
    db: Session = Depends(get_db),
) -> StudentResponse:
    """Get a single student by id, system-wide."""
    try:
        student = get_student_system_wide(db, student_id)
    except StudentNotFoundError:
        raise _STUDENT_NOT_FOUND

    return StudentResponse.model_validate(student)


@router.get("/stats", response_model=SystemStatisticsResponse)
def get_system_statistics_endpoint(
    admin: Admin = Depends(get_current_admin),
    db: Session = Depends(get_db),
) -> SystemStatisticsResponse:
    """Get basic system-wide platform statistics."""
    return get_system_statistics(db)


class SeedDemoDataResponse(BaseModel):
    """Response body for POST /admin/seed-demo-data."""

    already_seeded: bool
    output: str


@router.post("/seed-demo-data", response_model=SeedDemoDataResponse)
def seed_demo_data_endpoint(
    admin: Admin = Depends(get_current_admin),
) -> SeedDemoDataResponse:
    """
    Populate the database with a synthetic demonstration dataset: 6
    students, learning plans, varied content, sessions, quiz attempts,
    reflections, and engagement predictions — enough for a populated,
    realistic Analytics/dashboard demo instead of empty tables.

    This is a thin trigger around app/database/seed_synthetic_dataset.py,
    run exactly as documented (as a standalone script, driving the
    real HTTP API against this same running server) rather than
    reimplementing any of its logic here — the seeding behavior this
    endpoint exposes is identical to, and exercised by, that script's
    own direct command-line usage.

    Idempotent: the underlying script checks for a marker student_code
    prefix ("SEED-DEMO-") before inserting anything, so calling this
    endpoint when demo data already exists is always a safe no-op,
    never a duplicate insert. Restricted to Admin accounts, and (like
    seed_dev_admin) intended for non-production environments — running
    it against a real production database would create fake student
    accounts alongside real ones.
    """
    # Explicit cwd, anchored to this file's own location, rather than
    # relying on the parent uvicorn process's working directory. This
    # is the same class of fix as the DATABASE_URL/`.env` path
    # anchoring in core/config.py — subprocess.run() otherwise inherits
    # whatever directory the server happened to be launched from, and
    # `app.database.seed_synthetic_dataset` (like any `app.*` module)
    # is only importable with `backend/` as the working directory.
    from pathlib import Path

    backend_dir = Path(__file__).resolve().parent.parent.parent.parent

    result = subprocess.run(
        [sys.executable, "-m", "app.database.seed_synthetic_dataset"],
        capture_output=True,
        text=True,
        timeout=120,
        cwd=str(backend_dir),
    )

    output = (result.stdout or "") + (result.stderr or "")

    if result.returncode != 0:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Seeding failed: {output.strip()[-1000:]}",
        )

    already_seeded = "already present" in output

    return SeedDemoDataResponse(already_seeded=already_seeded, output=output.strip())
