"""
models/engagement_prediction.py

SQLAlchemy model for the `engagement_predictions` table.

An EngagementPrediction stores the ML model's (Decision Tree Classifier)
predicted engagement level for a LearningSession, along with the input
feature snapshots and a human-readable explanation. Storing the feature
snapshot (not just the output) preserves explainability, per Master
Specification Section 7: "Every recommendation should be explainable."

Relationship notes:
    - EngagementPrediction -> LearningSession: many-to-one (the "one"
      enforced by unique=True on learning_session_id). Cascade delete is
      configured on the LearningSession side.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.models.base_model import BaseModel


class EngagementPrediction(BaseModel):
    """
    Represents a single engagement prediction tied to one LearningSession.

    Inherits `id`, `created_at`, `updated_at` from BaseModel.
    """

    __tablename__ = "engagement_predictions"

    # One-to-one with LearningSession: unique + indexed enforces exactly
    # one EngagementPrediction per session.
    learning_session_id: Mapped[int] = mapped_column(
        ForeignKey("learning_sessions.id"),
        unique=True,
        index=True,
        nullable=False,
    )

    # --- Input feature snapshots (preserved for explainability) ---

    quiz_accuracy: Mapped[float | None] = mapped_column(Float, nullable=True)
    time_spent_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    idle_time_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    hint_usage_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    retry_count: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # --- Prediction output ---

    # Raw model output/confidence, e.g. 0.82.
    engagement_score: Mapped[float] = mapped_column(Float, nullable=False)

    # Simplified categorical label, validated in the app layer:
    # Low / Medium / High.
    engagement_label: Mapped[str] = mapped_column(String(10), nullable=False)

    # Human-readable rationale for the prediction.
    explanation: Mapped[str | None] = mapped_column(Text, nullable=True)

    predicted_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.now(),
        nullable=False,
    )

    # --- Relationships ---

    # The session this prediction belongs to.
    learning_session: Mapped["LearningSession"] = relationship(
        "LearningSession",
        back_populates="engagement_prediction",
    )

    def __repr__(self) -> str:
        """Developer-friendly representation, useful for debugging/logging."""
        return (
            f"<EngagementPrediction id={self.id} "
            f"label={self.engagement_label!r} score={self.engagement_score}>"
        )
