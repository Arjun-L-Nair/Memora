"""
models/conversation_history.py

SQLAlchemy model for the `conversation_history` table.

Persists every turn of the Mira companion chat so conversations survive
page reloads/logouts (important for ASD learners, who often rely on
being able to re-read prior exchanges). Also gives the LLM a sliding
window of prior context instead of treating each request as stateless.
"""

from __future__ import annotations

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base_model import BaseModel


class ConversationHistory(BaseModel):
    """A single turn (student or Mira) in a student's companion chat log."""

    __tablename__ = "conversation_history"

    student_id: Mapped[int] = mapped_column(
        ForeignKey("students.id"),
        index=True,
        nullable=False,
    )

    # "student" or "mira".
    role: Mapped[str] = mapped_column(String(10), nullable=False)

    message: Mapped[str] = mapped_column(Text, nullable=False)

    # Detected emotion for this turn (e.g. "frustrated", "curious",
    # "calm", "anxious", "happy", "confused"), null if not applicable
    # (e.g. system messages) or not yet classified.
    emotion_detected: Mapped[str | None] = mapped_column(String(20), nullable=True)

    student: Mapped["Student"] = relationship("Student", back_populates="conversation_history")

    def __repr__(self) -> str:
        return f"<ConversationHistory student_id={self.student_id} role={self.role!r}>"
