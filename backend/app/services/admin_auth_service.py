"""
services/admin_auth_service.py

Business logic for Admin authentication (Master Specification Section
4, 6: Administrator).

Reuses the generic, already-frozen security utilities directly:
    - verify_password() / hash_password() (core/security.py)
    - issue_token_pair() (auth_service.py) — fully generic over
      TokenRole, now including "admin"; no admin-specific token
      issuance logic needed.
    - AuthenticationError (auth_service.py) — reused rather than
      duplicated, same "don't leak account existence" reasoning as
      Teacher/Student authentication.

Admin has no is_active column in the frozen schema (see Phase 13
planning) — authentication here checks only email + password, with no
active/inactive concept, consistent with api/deps.get_current_admin
and auth_service.refresh_access_token's admin branch.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import verify_password
from app.models import Admin
from app.services.auth_service import AuthenticationError

__all__ = ["AuthenticationError", "authenticate_admin"]


def authenticate_admin(db: Session, email: str, password: str) -> Admin:
    """
    Verify an admin's email + password.

    Returns the Admin on success. Raises AuthenticationError if the
    account does not exist or the password is wrong. Intentionally
    generic (same message regardless of cause) to avoid leaking which
    admin emails exist, matching the pattern used for Teacher/Student
    authentication.
    """
    admin = db.execute(
        select(Admin).where(Admin.email == email)
    ).scalar_one_or_none()

    if admin is None:
        raise AuthenticationError("Invalid credentials.")

    if not verify_password(password, admin.password_hash):
        raise AuthenticationError("Invalid credentials.")

    return admin
