"""
models/learning_session.py

SQLAlchemy model for the `learning_sessions` table.

A LearningSession represents a single instance of a student engaging with
assigned content (e.g., one sitting of "Today's Learning"). It tracks
session-specific data — time spent, quiz attempts, engagement prediction,
and reflection — and feeds the Analytics Dashboard and Adaptive Suggestions
(see Master Specification, Section 10).

Design principle:
    A LearningSession becomes a historical record once its `status` is
    "completed". This model does NOT enforce immutability at the database
    level — that responsibility belongs to the service layer, which should
    treat completed sessions as read-only except through explicit,
    deliberate administrative operations.

Relationship notes:
    - LearningSession -> Student: many-to-one. NO cascade delete
      (soft-delete philosophy — session history persists).
    - LearningSession -> LearningPlan: many-to-one. NO cascade delete,
      same reasoning.
    - LearningSession -> LearningContent: many-to-one. NO cascade delete,
      same reasoning.
    - LearningSession -> QuizAttempt: one-to-one, cascade delete-orphan.
      A QuizAttempt has no independent meaning outside its session.
    - LearningSession -> EngagementPrediction: one-to-one, cascade
      delete-orphan. Same reasoning as QuizAttempt.
    - LearningSession -> LearningReflection: one-to-one, cascade
      delete-orphan. Same reasoning as QuizAttempt.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base_model import BaseModel


class LearningSession(BaseModel):
    """
    Represents a single instance of a student engaging with assigned content.

    Inherits `id`, `created_at`, `updated_at` from BaseModel.
    """

    __tablename__ = "learning_sessions"

    # --- Foreign Keys ---

    student_id: Mapped[int] = mapped_column(
        ForeignKey("students.id"),
        index=True,
        nullable=False,
    )

    learning_plan_id: Mapped[int] = mapped_column(
        ForeignKey("learning_plans.id"),
        index=True,
        nullable=False,
    )

    learning_content_id: Mapped[int] = mapped_column(
        ForeignKey("learning_contents.id"),
        index=True,
        nullable=False,
    )

    # --- Session timing / engagement indicators ---

    started_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    time_spent_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)

    idle_time_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)

    hint_usage_count: Mapped[int] = mapped_column(
        Integer, default=0, server_default="0", nullable=False
    )

    retry_count: Mapped[int] = mapped_column(
        Integer, default=0, server_default="0", nullable=False
    )

    # Session lifecycle status. Validated in the app layer:
    # started / completed / abandoned.
    status: Mapped[str] = mapped_column(
        String(20),
        default="started",
        server_default="started",
        nullable=False,
    )

    # Snapshot of the student's adaptive difficulty at the time of this
    # session, kept for historical analytics even if the student's current
    # difficulty later changes.
    difficulty_level_at_session: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )

    # --- Relationships ---

    student: Mapped["Student"] = relationship(
        "Student",
        back_populates="learning_sessions",
    )

    learning_plan: Mapped["LearningPlan"] = relationship(
        "LearningPlan",
        back_populates="learning_sessions",
    )

    learning_content: Mapped["LearningContent"] = relationship(
        "LearningContent",
        back_populates="learning_sessions",
    )

    # One-to-one: a session produces at most one quiz attempt.
    quiz_attempt: Mapped["QuizAttempt | None"] = relationship(
        "QuizAttempt",
        back_populates="learning_session",
        uselist=False,
        cascade="all, delete-orphan",
    )

    # One-to-one: a session produces at most one engagement prediction.
    engagement_prediction: Mapped["EngagementPrediction | None"] = relationship(
        "EngagementPrediction",
        back_populates="learning_session",
        uselist=False,
        cascade="all, delete-orphan",
    )

    # One-to-one: a session produces at most one learning reflection.
    learning_reflection: Mapped["LearningReflection | None"] = relationship(
        "LearningReflection",
        back_populates="learning_session",
        uselist=False,
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        """Developer-friendly representation, useful for debugging/logging."""
        return f"<LearningSession id={self.id} status={self.status!r}>"
