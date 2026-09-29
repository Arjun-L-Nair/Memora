"""
database/seed_dev_admin.py

Development Admin bootstrap.

Intended hierarchy (per Master Specification, Section 4/6):
    Admin -> creates/provisions Teachers -> Teachers create Students ->
    Students use the platform.

There is no admin-registration endpoint (by design — Admin accounts are
provisioned, not self-registered), so a completely fresh development
database has no way to create the FIRST admin account through the API.
This module exists solely to solve that one bootstrapping problem.

Behavior:
    - Only ever creates an admin if NO admin exists yet in the database
      at all (not per-email, unlike seed_dev_teacher.py — this is a
      one-time hierarchy bootstrap, not a reusable per-account seed).
    - Requires both DEV_ADMIN_EMAIL and DEV_ADMIN_PASSWORD to be set in
      settings (see core/config.py); if either is missing, this no-ops
      silently so a fresh checkout without those variables configured
      still starts up normally.
    - NEVER overwrites, resets, or modifies an existing Admin account,
      no matter what DEV_ADMIN_EMAIL/DEV_ADMIN_PASSWORD currently
      contain — if any admin row exists, this function does nothing.
    - Uses the same hash_password() utility already used everywhere
      else in the codebase — no new hashing logic.

This does NOT change the /admin/login contract, teacher/student
authentication, or any other frozen Phase 1-15/16 behavior. It only
inserts one row, under the conditions above, before the app starts
accepting requests.
"""

from __future__ import annotations

from sqlalchemy import select

from app.core.config import settings
from app.core.security import hash_password
from app.database.session import SessionLocal
from app.models import Admin


def seed_dev_admin() -> None:
    """
    Insert exactly one Admin account, if and only if:
        1. No Admin account exists yet in the database, AND
        2. settings.DEV_ADMIN_EMAIL and settings.DEV_ADMIN_PASSWORD are
           both configured.

    Safe to call on every application startup — idempotent, and never
    touches an existing Admin account.
    """
    if not settings.DEV_ADMIN_EMAIL or not settings.DEV_ADMIN_PASSWORD:
        print("DEV_ADMIN_EMAIL/DEV_ADMIN_PASSWORD not configured; skipping admin bootstrap.")
        return

    db = SessionLocal()
    try:
        existing_admin = db.execute(select(Admin)).scalars().first()
        if existing_admin is not None:
            print("An admin account already exists; skipping admin bootstrap.")
            return

        admin = Admin(
            full_name="Development Admin",
            email=settings.DEV_ADMIN_EMAIL,
            password_hash=hash_password(settings.DEV_ADMIN_PASSWORD),
        )
        db.add(admin)
        db.commit()
        print(f"Bootstrapped initial admin account ({settings.DEV_ADMIN_EMAIL}).")
    finally:
        db.close()


if __name__ == "__main__":
    # python -m app.database.seed_dev_admin
    seed_dev_admin()
