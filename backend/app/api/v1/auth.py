"""
api/v1/auth.py

Authentication router (Master Specification Section 6).

Endpoints:
    POST /auth/teacher/login  - Email + Password -> access/refresh tokens.
    POST /auth/student/login  - Student ID + PIN -> access/refresh tokens.
    POST /auth/refresh        - Refresh token -> new access token.

This router contains no business logic or database access itself — it
only parses requests, calls the service layer (app.services.auth_service),
translates service-layer exceptions into HTTP responses, and returns the
appropriate schema. Per the architecture rules (Section 11), all real
logic lives in the service layer.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.auth import (
    RefreshTokenRequest,
    StudentLoginRequest,
    TeacherLoginRequest,
    TokenResponse,
)
from app.services.auth_service import (
    AuthenticationError,
    InvalidRefreshTokenError,
    authenticate_student,
    authenticate_teacher,
    issue_token_pair,
    refresh_access_token,
)

router = APIRouter(prefix="/auth", tags=["Authentication"])

_INVALID_CREDENTIALS = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Invalid credentials.",
)

_INVALID_REFRESH_TOKEN = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Invalid or expired refresh token.",
)


@router.post("/teacher/login", response_model=TokenResponse)
def teacher_login(
    payload: TeacherLoginRequest,
    db: Session = Depends(get_db),
) -> TokenResponse:
    """Authenticate a teacher by email + password and issue tokens."""
    try:
        teacher = authenticate_teacher(db, payload.email, payload.password)
    except AuthenticationError:
        raise _INVALID_CREDENTIALS

    access_token, refresh_token = issue_token_pair(
        subject=str(teacher.id), role="teacher"
    )
    return TokenResponse(access_token=access_token, refresh_token=refresh_token)


@router.post("/student/login", response_model=TokenResponse)
def student_login(
    payload: StudentLoginRequest,
    db: Session = Depends(get_db),
) -> TokenResponse:
    """Authenticate a student by Student ID + 4-digit PIN and issue tokens."""
    try:
        student = authenticate_student(db, payload.student_code, payload.pin)
    except AuthenticationError:
        raise _INVALID_CREDENTIALS

    access_token, refresh_token = issue_token_pair(
        subject=str(student.id), role="student"
    )
    return TokenResponse(access_token=access_token, refresh_token=refresh_token)


@router.post("/refresh", response_model=TokenResponse)
def refresh(
    payload: RefreshTokenRequest,
    db: Session = Depends(get_db),
) -> TokenResponse:
    """
    Exchange a valid refresh token for a NEW access/refresh token pair
    (refresh-token rotation). The original refresh token is consumed —
    it is not returned again and should be discarded by the caller.
    """
    try:
        new_access_token, new_refresh_token, _subject, _role = refresh_access_token(
            db, payload.refresh_token
        )
    except InvalidRefreshTokenError:
        raise _INVALID_REFRESH_TOKEN

    return TokenResponse(
        access_token=new_access_token,
        refresh_token=new_refresh_token,
    )
