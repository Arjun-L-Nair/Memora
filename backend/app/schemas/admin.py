"""
schemas/admin.py

Pydantic request/response schemas for the Admin module (Master
Specification Section 4, 6: Administrator).

Reuse over duplication:
    - Login response reuses schemas.auth.TokenResponse directly — the
      shape (access_token, refresh_token, token_type) is identical to
      Teacher/Student login, so no new response type is defined here.
    - Student administrative listing reuses schemas.student.StudentResponse
      directly — it already excludes pin_hash and is list-compatible
      (list[StudentResponse]), so no separate "admin student" schema is
      created. See api/v1/admin.py (Module 6) for its usage.

New schemas here are for genuinely new shapes: Admin login request,
Teacher creation (admin sets the initial password directly, mirroring
how StudentCreate lets a teacher set a student's initial PIN — neither
Teachers nor Students self-register), Teacher's admin-facing response
(password_hash never included, same pattern as StudentResponse), and
basic system statistics (plain ints, safe at zero).
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class AdminLoginRequest(BaseModel):
    """Request body for POST /admin/login."""

    email: EmailStr
    password: str = Field(..., min_length=1)


class TeacherCreateByAdmin(BaseModel):
    """
    Request body for POST /admin/teachers (admin creates a new teacher
    account). Teachers cannot self-register, so the admin sets the
    initial password directly — mirroring how a teacher sets a
    student's initial PIN in StudentCreate (Phase 5).
    """

    full_name: str = Field(..., min_length=1, max_length=100)
    email: EmailStr
    password: str = Field(..., min_length=1)
    organization_name: str | None = Field(default=None, max_length=150)


class TeacherAdminResponse(BaseModel):
    """
    Response body for admin-facing Teacher endpoints. Never includes
    password_hash — same exclusion pattern as StudentResponse.
    """

    model_config = ConfigDict(from_attributes=True)

    id: int
    full_name: str
    email: str
    organization_name: str | None
    is_active: bool


class SystemStatisticsResponse(BaseModel):
    """
    Response body for GET /admin/stats. Basic, zero-safe counts only —
    no enterprise-style reporting, per Phase 13 scope.
    """

    total_teachers: int
    active_teachers: int
    inactive_teachers: int
    total_students: int
    active_students: int
    inactive_students: int
    total_learning_sessions: int
    total_quiz_attempts: int
