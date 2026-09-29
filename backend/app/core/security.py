"""
core/security.py

Security utilities: password/PIN hashing and JWT token encode/decode.

Consumes `settings` from the frozen `app.core.config` module — no new
configuration values are introduced here; `SECRET_KEY`, `JWT_ALGORITHM`,
`ACCESS_TOKEN_EXPIRE_MINUTES`, and `REFRESH_TOKEN_EXPIRE_DAYS` already
exist there.

--------------------------------------------------------------------------
Why explicit hash_password/verify_password and hash_pin/verify_pin,
instead of one generic hash_secret/verify_secret pair?
--------------------------------------------------------------------------
Teacher passwords and Student PINs are different domain concepts with
different validation rules (a PIN is exactly 4 digits; a password has
its own — currently unconstrained — rules) even though both currently
share the same underlying bcrypt mechanism. Explicit, separately named
functions:
    - Make call sites self-documenting (`verify_pin(...)` vs a generic
      `verify_secret(...)` that could be misapplied to the wrong field).
    - Give each concept its own seam to diverge later (e.g. adding
      PIN-specific format validation) without changing a shared,
      ambiguously-named function's contract.
Both still delegate to one private `_hash`/`_verify` pair, so there is
no duplicated hashing logic — only the naming is domain-specific.

--------------------------------------------------------------------------
Why refresh tokens are implemented (not just "good practice")
--------------------------------------------------------------------------
`app.core.config.Settings` (frozen, Phase 3) already declares
`REFRESH_TOKEN_EXPIRE_DAYS` as a required, validated configuration
field. That field was committed to the architecture before Phase 4
began. If refresh tokens were not implemented, this configuration value
would be dead — validated at startup but never consumed anywhere,
which violates "avoid duplicated logic" / no-unused-configuration in
reverse (unused config is just as much an inconsistency as duplicated
logic). Implementing refresh token issuance is therefore required to
make the already-frozen configuration schema consistent with the
running application, not an invented feature.

--------------------------------------------------------------------------
Why a single decode_token() API, not two decode functions
--------------------------------------------------------------------------
Only one JWT library (`python-jose`) is used internally, and only one
call site (the auth dependencies) needs to decode tokens. A single
`decode_token()` that translates `jose.JWTError` into this module's own
`InvalidTokenError` is simpler than exposing both a raw
library-exception-raising function and a "safe" wrapper — there is no
second caller that needs the raw `jose.JWTError`, so the extra API
surface added no value.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Literal

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import settings

# --- Hashing (shared implementation, domain-specific names) ---

_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def _hash(plain_value: str) -> str:
    """Hash a plaintext value with bcrypt. Internal, shared by password/PIN helpers."""
    return _pwd_context.hash(plain_value)


def _verify(plain_value: str, hashed_value: str) -> bool:
    """
    Verify a plaintext value against a bcrypt hash. Returns False (never
    raises) for a malformed/corrupt hash, so callers get a plain boolean.
    """
    try:
        return _pwd_context.verify(plain_value, hashed_value)
    except (ValueError, TypeError):
        return False


def hash_password(plain_password: str) -> str:
    """Hash a teacher's plaintext password for storage in Teacher.password_hash."""
    return _hash(plain_password)


def verify_password(plain_password: str, password_hash: str) -> bool:
    """Verify a teacher's plaintext password against Teacher.password_hash."""
    return _verify(plain_password, password_hash)


def hash_pin(plain_pin: str) -> str:
    """Hash a student's plaintext 4-digit PIN for storage in Student.pin_hash."""
    return _hash(plain_pin)


def verify_pin(plain_pin: str, pin_hash: str) -> bool:
    """Verify a student's plaintext PIN against Student.pin_hash."""
    return _verify(plain_pin, pin_hash)


# --- JWT Tokens ---

TokenType = Literal["access", "refresh"]
TokenRole = Literal["teacher", "student", "admin"]


class InvalidTokenError(Exception):
    """Raised by decode_token() when a token is malformed, expired, or unsigned correctly."""


def _create_token(
    subject: str,
    role: TokenRole,
    token_type: TokenType,
    expires_delta: timedelta,
) -> str:
    """Internal helper shared by create_access_token() / create_refresh_token()."""
    now = datetime.now(timezone.utc)
    payload: dict[str, Any] = {
        "sub": subject,
        "role": role,
        "type": token_type,
        "iat": now,
        "exp": now + expires_delta,
        # Unique token ID. JWT "iat"/"exp" claims are encoded with only
        # second-level precision, so two tokens issued for the same
        # subject/role/type within the same wall-clock second would
        # otherwise be byte-for-byte identical (same payload -> same
        # signature). This matters specifically for refresh-token
        # rotation, where each exchange must produce a genuinely new,
        # distinguishable token even if it happens within the same
        # second as the previous issuance.
        "jti": str(uuid.uuid4()),
    }
    return jwt.encode(
        payload,
        settings.SECRET_KEY.get_secret_value(),
        algorithm=settings.JWT_ALGORITHM,
    )


def create_access_token(subject: str, role: TokenRole) -> str:
    """
    Create a short-lived access token for the given subject/role.

    `subject` is the string form of the Teacher.id or Student.id.
    Expiry is controlled by settings.ACCESS_TOKEN_EXPIRE_MINUTES.
    """
    return _create_token(
        subject=subject,
        role=role,
        token_type="access",
        expires_delta=timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
    )


def create_refresh_token(subject: str, role: TokenRole) -> str:
    """
    Create a longer-lived refresh token for the given subject/role.

    Expiry is controlled by settings.REFRESH_TOKEN_EXPIRE_DAYS. Required
    to make use of that frozen configuration field — see module
    docstring for the full justification.
    """
    return _create_token(
        subject=subject,
        role=role,
        token_type="refresh",
        expires_delta=timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
    )


def decode_token(token: str) -> dict[str, Any]:
    """
    Decode and verify a JWT's signature and expiry.

    Raises this module's own `InvalidTokenError` (not `jose.JWTError`)
    on any failure — malformed token, invalid signature, or expiry —
    so callers (api/deps.py) depend only on this module's exception
    type, not on which JWT library is used internally.
    """
    try:
        return jwt.decode(
            token,
            settings.SECRET_KEY.get_secret_value(),
            algorithms=[settings.JWT_ALGORITHM],
        )
    except JWTError as exc:
        raise InvalidTokenError(str(exc)) from exc
