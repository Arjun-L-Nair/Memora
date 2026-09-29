"""
schemas/auth.py

Pydantic request/response schemas for authentication (Master
Specification Section 6).

Two login flows, per spec:
    - Teacher: Email + Password -> JWT (access + refresh).
    - Student: Student ID + 4-digit PIN -> short-lived JWT (access +
      refresh, for consistency with the teacher flow and to make use of
      the frozen REFRESH_TOKEN_EXPIRE_DAYS setting — see
      app/core/security.py for the full justification).

No password policy is enforced here beyond "non-empty" — the spec does
not define one, and inventing one would exceed ticket scope. The PIN,
however, is explicitly specified as a "4-digit PIN", so it is validated
to match exactly that shape.
"""

from __future__ import annotations

from pydantic import BaseModel, EmailStr, Field


class TeacherLoginRequest(BaseModel):
    """Request body for POST /auth/teacher/login."""

    email: EmailStr
    password: str = Field(..., min_length=1)


class StudentLoginRequest(BaseModel):
    """Request body for POST /auth/student/login."""

    student_code: str = Field(..., min_length=1)
    pin: str = Field(
        ...,
        pattern=r"^\d{4}$",
        description="Exactly 4 numeric digits.",
    )


class RefreshTokenRequest(BaseModel):
    """Request body for POST /auth/refresh."""

    refresh_token: str = Field(..., min_length=1)


class TokenResponse(BaseModel):
    """Response body returned by all successful login/refresh endpoints."""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"
