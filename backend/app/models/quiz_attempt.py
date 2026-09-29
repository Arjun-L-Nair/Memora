"""
models/quiz_attempt.py

SQLAlchemy model for the `quiz_attempts` table.

A QuizAttempt stores the AI-generated (or fallback template-based) quiz
and the student's answers/results for a given LearningSession. Per the
frozen schema, this is a strict one-to-one child of LearningSession —
enforced via a unique foreign key.

Relationship notes:
    - QuizAttempt -> LearningSession: many-to-one (the "one" enforced by
      unique=True on learning_session_id). Cascade delete is configured
      on the LearningSession side (parent owns the delete-orphan rule).
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base_model import BaseModel


class QuizAttempt(BaseModel):
    """
    Represents a single quiz attempt tied to one LearningSession.

    Inherits `id`, `created_at`, `updated_at` from BaseModel.
    """

    __tablename__ = "quiz_attempts"

    # One-to-one with LearningSession: unique + indexed enforces exactly
    # one QuizAttempt per session.
    learning_session_id: Mapped[int] = mapped_column(
        ForeignKey("learning_sessions.id"),
        unique=True,
        index=True,
        nullable=False,
    )

    # Origin of the quiz: "ai_generated" or "template_fallback".
    quiz_source: Mapped[str] = mapped_column(String(20), nullable=False)

    # Serialized quiz questions/options.
    questions_json: Mapped[str] = mapped_column(Text, nullable=False)

    # Serialized student answers. Null until the student submits.
    answers_json: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Percentage correct, set on submission.
    score: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Used directly as an engagement indicator (Section 7).
    accuracy: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Difficulty level this quiz was generated at.
    difficulty_level: Mapped[str] = mapped_column(String(20), nullable=False)

    # How long the student took to finish the quiz — an engagement feature.
    time_taken_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Total number of questions in the quiz, for analytics
    # (e.g., accuracy = correct / total_questions).
    total_questions: Mapped[int] = mapped_column(Integer, nullable=False)

    submitted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    # --- Relationships ---

    # The session this quiz attempt belongs to.
    learning_session: Mapped["LearningSession"] = relationship(
        "LearningSession",
        back_populates="quiz_attempt",
    )

    def __repr__(self) -> str:
        """Developer-friendly representation, useful for debugging/logging."""
        return f"<QuizAttempt id={self.id} session_id={self.learning_session_id}>"
