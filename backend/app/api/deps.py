"""
api/deps.py

FastAPI dependencies for authentication/authorization.

Extracts the JWT from the `Authorization: Bearer <token>` header,
validates it, and loads the corresponding account from the database.
Two role-specific dependencies are exposed:

    - get_current_teacher: requires a valid ACCESS token with role="teacher".
    - get_current_student: requires a valid ACCESS token with role="student".

A refresh token is never accepted here — only "type": "access" tokens
authenticate a request; refresh tokens are only valid at the dedicated
refresh endpoint (see services/auth_service.py, api/v1/auth.py).
"""

from __future__ import annotations

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import InvalidTokenError, decode_token
from app.database import get_db
from app.models import Admin, Student, Teacher

# HTTPBearer extracts the raw "Authorization: Bearer <token>" header.
# auto_error=True means FastAPI itself returns 401 if the header is
# missing entirely, before this module's code even runs.
_bearer_scheme = HTTPBearer(auto_error=True)

_CREDENTIALS_ERROR = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Could not validate credentials.",
    headers={"WWW-Authenticate": "Bearer"},
)


def _get_current_account(
    credentials: HTTPAuthorizationCredentials,
    db: Session,
    expected_role: str,
    model: type[Teacher] | type[Student],
) -> Teacher | Student:
    """
    Shared implementation for get_current_teacher() / get_current_student().

    Decodes the token, checks it is an access token for the expected
    role, loads the matching account, and confirms it is still active.
    Raises HTTPException(401) on any failure.
    """
    try:
        payload = decode_token(credentials.credentials)
    except InvalidTokenError:
        raise _CREDENTIALS_ERROR

    if payload.get("type") != "access" or payload.get("role") != expected_role:
        raise _CREDENTIALS_ERROR

    try:
        account_id = int(payload["sub"])
    except (KeyError, ValueError, TypeError):
        raise _CREDENTIALS_ERROR

    account = db.execute(
        select(model).where(model.id == account_id)
    ).scalar_one_or_none()

    if account is None or not account.is_active:
        raise _CREDENTIALS_ERROR

    return account


def get_current_teacher(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer_scheme),
    db: Session = Depends(get_db),
) -> Teacher:
    """
    FastAPI dependency: resolve the authenticated Teacher from the
    request's Authorization header. Use in routers that require a
    logged-in teacher:

        @router.get("/teachers/me")
        def read_me(teacher: Teacher = Depends(get_current_teacher)):
            ...
    """
    account = _get_current_account(credentials, db, "teacher", Teacher)
    assert isinstance(account, Teacher)  # narrows type for callers
    return account


def get_current_student(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer_scheme),
    db: Session = Depends(get_db),
) -> Student:
    """
    FastAPI dependency: resolve the authenticated Student from the
    request's Authorization header. Use in routers that require a
    logged-in student:

        @router.get("/students/me")
        def read_me(student: Student = Depends(get_current_student)):
            ...
    """
    account = _get_current_account(credentials, db, "student", Student)
    assert isinstance(account, Student)  # narrows type for callers
    return account


def get_current_admin(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer_scheme),
    db: Session = Depends(get_db),
) -> Admin:
    """
    FastAPI dependency: resolve the authenticated Admin from the
    request's Authorization header.

    Does not reuse _get_current_account() because that helper checks
    account.is_active, which the frozen Admin model does not have —
    Admin accounts have no deactivation concept in the current schema.
    """
    try:
        payload = decode_token(credentials.credentials)
    except InvalidTokenError:
        raise _CREDENTIALS_ERROR

    if payload.get("type") != "access" or payload.get("role") != "admin":
        raise _CREDENTIALS_ERROR

    try:
        account_id = int(payload["sub"])
    except (KeyError, ValueError, TypeError):
        raise _CREDENTIALS_ERROR

    admin = db.execute(
        select(Admin).where(Admin.id == account_id)
    ).scalar_one_or_none()

    if admin is None:
        raise _CREDENTIALS_ERROR

    return admin
