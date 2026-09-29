"""
models/emotion_log.py

SQLAlchemy model for the `emotion_logs` table.

Records point-in-time emotional check-ins and detected emotions (from
chat, reflections, or explicit check-in prompts) so trends can be
plotted over time and fed into the early-warning system.
"""

from __future__ import annotations

from sqlalchemy import Float, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base_model import BaseModel


class EmotionLog(BaseModel):
    """A single emotion data point for a student."""

    __tablename__ = "emotion_logs"

    student_id: Mapped[int] = mapped_column(
        ForeignKey("students.id"),
        index=True,
        nullable=False,
    )

    # One of the 6 core emotions the classifier targets: happy, calm,
    # frustrated, anxious, confused, sad.
    emotion: Mapped[str] = mapped_column(String(20), nullable=False)

    # Classifier confidence, 0.0-1.0. Null for explicit self-reports.
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Where this reading came from: "check_in", "chat", "reflection".
    source: Mapped[str] = mapped_column(String(20), nullable=False)

    student: Mapped["Student"] = relationship("Student", back_populates="emotion_logs")

    def __repr__(self) -> str:
        return f"<EmotionLog student_id={self.student_id} emotion={self.emotion!r}>"
