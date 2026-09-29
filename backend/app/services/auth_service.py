"""
services/auth_service.py

Business logic for authentication (Master Specification Section 6).

Per the architecture rules (Section 11), all database access and
credential-verification logic lives here — routers only call these
functions and translate the results/exceptions into HTTP responses.
No direct database queries belong in the router.

Exception design:
    A single `AuthenticationError` covers "account not found", "wrong
    password/PIN", and "inactive account". These are deliberately not
    distinguished so a caller cannot use error responses to enumerate
    which student codes/teacher emails exist in the system.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import (
    TokenRole,
    create_access_token,
    create_refresh_token,
    decode_token,
    verify_password,
    verify_pin,
    InvalidTokenError,
)
from app.models import Admin, Student, Teacher


class AuthenticationError(Exception):
    """
    Raised when teacher/student credentials are invalid, or the account
    is inactive. Intentionally generic — see module docstring.
    """


class InvalidRefreshTokenError(Exception):
    """Raised when a refresh token is malformed, expired, or not of type 'refresh'."""


def _require_active(account: Teacher | Student | None) -> Teacher | Student:
    """
    Shared validation: raise AuthenticationError if the account was not
    found or is inactive; otherwise return it unchanged.

    Used by both authenticate_teacher() and authenticate_student() (and
    by refresh_access_token()) so the "not found or inactive" check is
    defined in exactly one place, even though Teacher and Student are
    unrelated model classes.
    """
    if account is None or not account.is_active:
        raise AuthenticationError("Invalid credentials.")
    return account


def authenticate_teacher(db: Session, email: str, password: str) -> Teacher:
    """
    Verify a teacher's email + password.

    Returns the Teacher on success. Raises AuthenticationError if the
    account does not exist, the password is wrong, or the account is
    inactive.
    """
    teacher = db.execute(
        select(Teacher).where(Teacher.email == email)
    ).scalar_one_or_none()
    teacher = _require_active(teacher)

    if not verify_password(password, teacher.password_hash):
        raise AuthenticationError("Invalid credentials.")

    return teacher


def authenticate_student(db: Session, student_code: str, pin: str) -> Student:
    """
    Verify a student's Student ID (student_code) + 4-digit PIN.

    Returns the Student on success. Raises AuthenticationError if the
    account does not exist, the PIN is wrong, or the account is inactive.
    """
    student = db.execute(
        select(Student).where(Student.student_code == student_code)
    ).scalar_one_or_none()
    student = _require_active(student)

    if not verify_pin(pin, student.pin_hash):
        raise AuthenticationError("Invalid credentials.")

    return student


def issue_token_pair(subject: str, role: TokenRole) -> tuple[str, str]:
    """
    Issue a new (access_token, refresh_token) pair for the given
    subject/role. Used identically after a successful teacher or
    student login.
    """
    access_token = create_access_token(subject=subject, role=role)
    refresh_token = create_refresh_token(subject=subject, role=role)
    return access_token, refresh_token


def refresh_access_token(db: Session, refresh_token: str) -> tuple[str, str, str, TokenRole]:
    """
    Validate a refresh token and issue a NEW (access_token, refresh_token)
    pair — refresh-token rotation. The original refresh token is not
    reused or returned; a fresh one is issued alongside the new access
    token. This limits how long any single refresh token stays valid
    and reduces the impact of a leaked refresh token, since it becomes
    unusable the moment it is exchanged.

    In addition to verifying the token itself (signature, expiry, and
    that it is actually a refresh token), this re-checks the database
    to confirm the corresponding Teacher/Student still exists and is
    still active. Without this check, a refresh token issued before an
    account was deactivated (or, hypothetically, deleted) would remain
    usable to mint fresh tokens for the rest of its validity window —
    re-validating against the database closes that gap.

    Returns (new_access_token, new_refresh_token, subject, role).
    Raises InvalidRefreshTokenError if the token is malformed/expired,
    is not actually a refresh token, or the corresponding account no
    longer exists or is inactive.
    """
    try:
        payload = decode_token(refresh_token)
    except InvalidTokenError as exc:
        raise InvalidRefreshTokenError(str(exc)) from exc

    if payload.get("type") != "refresh":
        raise InvalidRefreshTokenError("Token is not a refresh token.")

    subject: str = payload["sub"]
    role: TokenRole = payload["role"]

    if role == "teacher":
        model = Teacher
    elif role == "student":
        model = Student
    else:
        model = Admin

    account = db.execute(
        select(model).where(model.id == int(subject))
    ).scalar_one_or_none()

    if role == "admin":
        # Admin has no is_active column in the frozen schema —
        # existence is the only check available/applicable for this role.
        if account is None:
            raise InvalidRefreshTokenError("Account no longer exists.")
    else:
        try:
            _require_active(account)
        except AuthenticationError as exc:
            raise InvalidRefreshTokenError(
                "Account no longer exists or is inactive."
            ) from exc

    new_access_token, new_refresh_token = issue_token_pair(subject=subject, role=role)
    return new_access_token, new_refresh_token, subject, role
