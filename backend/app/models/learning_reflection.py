"""
models/learning_reflection.py

SQLAlchemy model for the `learning_reflections` table.

A LearningReflection stores the AI-generated (or fallback template-based)
end-of-session reflection shown to the student. Per Master Specification
Section 7 (LLM Reliability), Ollama requests must timeout after 15 seconds
and fall back to template-based reflections if generation fails.

Relationship notes:
    - LearningReflection -> LearningSession: many-to-one (the "one"
      enforced by unique=True on learning_session_id). Cascade delete is
      configured on the LearningSession side.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.models.base_model import BaseModel


class LearningReflection(BaseModel):
    """
    Represents a single learning reflection tied to one LearningSession.

    Inherits `id`, `created_at`, `updated_at` from BaseModel.
    """

    __tablename__ = "learning_reflections"

    # One-to-one with LearningSession: unique + indexed enforces exactly
    # one LearningReflection per session.
    learning_session_id: Mapped[int] = mapped_column(
        ForeignKey("learning_sessions.id"),
        unique=True,
        index=True,
        nullable=False,
    )

    # The reflection text shown to the student.
    content: Mapped[str] = mapped_column(Text, nullable=False)

    # Identifies whether the reflection came from the LLM or the fallback
    # template. Validated in the app layer: ollama / template.
    generated_by: Mapped[str] = mapped_column(String(20), nullable=False)

    generated_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.now(),
        nullable=False,
    )

    # --- Relationships ---

    # The session this reflection belongs to.
    learning_session: Mapped["LearningSession"] = relationship(
        "LearningSession",
        back_populates="learning_reflection",
    )

    def __repr__(self) -> str:
        """Developer-friendly representation, useful for debugging/logging."""
        return (
            f"<LearningReflection id={self.id} "
            f"generated_by={self.generated_by!r}>"
        )
