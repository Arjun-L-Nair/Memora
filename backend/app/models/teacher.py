"""
models/teacher.py

SQLAlchemy model for the `teachers` table.

Teachers authenticate via email/password + JWT (see Master Specification,
Section 6). A teacher creates and manages students, and assigns learning
plans to them.

Relationship notes:
    - Teacher -> Student: one-to-many. NO cascade delete. Deleting a
      teacher must be handled explicitly in the service layer (e.g.
      reassigning or blocking deletion), not silently cascaded here.
    - Teacher -> LearningPlan: one-to-many. Same rule — NO cascade delete.
"""

from __future__ import annotations

from sqlalchemy import Boolean, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import true

from app.models.base_model import BaseModel


class Teacher(BaseModel):
    """
    Represents a teacher account.

    Inherits `id`, `created_at`, `updated_at` from BaseModel.
    """

    __tablename__ = "teachers"

    # Full display name of the teacher.
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

    # School or organization name. Optional.
    organization_name: Mapped[str | None] = mapped_column(
        String(150),
        nullable=True,
    )

    # Soft-disable flag for deactivating a teacher account without deleting it.
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        server_default=true(),
        nullable=False,
    )

    # --- Relationships ---

    # All students created/owned by this teacher.
    # No cascade delete: removing a teacher does not automatically remove
    # their students; that decision belongs to the service layer.
    students: Mapped[list["Student"]] = relationship(
        "Student",
        back_populates="teacher",
    )

    # All learning plans assigned by this teacher.
    # No cascade delete, same reasoning as above.
    learning_plans: Mapped[list["LearningPlan"]] = relationship(
        "LearningPlan",
        back_populates="teacher",
    )

    def __repr__(self) -> str:
        """Developer-friendly representation, useful for debugging/logging."""
        return f"<Teacher id={self.id} email={self.email!r}>"
