"""
models/admin.py

SQLAlchemy model for the `admins` table.

Admin accounts are intentionally lightweight (see Master Specification,
Section 4): they manage teachers/students and view basic platform
statistics, but they do not own any foreign-key relationships to other
domain tables. Admin oversight is handled at the service/query layer,
not via ORM relationships.
"""

from __future__ import annotations

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base_model import BaseModel


class Admin(BaseModel):
    """
    Represents a platform administrator account.

    Inherits `id`, `created_at`, `updated_at` from BaseModel.
    """

    __tablename__ = "admins"

    # Full display name of the administrator.
    full_name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    # Login email. Indexed + unique since it's used for authentication lookups.
    email: Mapped[str] = mapped_column(
        String(150),
        unique=True,
        index=True,
        nullable=False,
    )

    # Hashed password (never store plaintext).
    password_hash: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    def __repr__(self) -> str:
        """Developer-friendly representation, useful for debugging/logging."""
        return f"<Admin id={self.id} email={self.email!r}>"
