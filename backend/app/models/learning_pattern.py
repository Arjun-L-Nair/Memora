"""
models/learning_pattern.py

SQLAlchemy model for the `learning_patterns` table.

Stores ML-derived, per-student behavioral patterns recomputed
periodically by the ML pipeline (app/ml). Distinct from SensoryProfile
(self-reported/set preferences) — these fields are *inferred* from
session history.
"""

from __future__ import annotations

from sqlalchemy import Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base_model import BaseModel


class LearningPattern(BaseModel):
    """ML-inferred learning behavior pattern for a single student."""

    __tablename__ = "learning_patterns"

    student_id: Mapped[int] = mapped_column(
        ForeignKey("students.id"),
        unique=True,
        index=True,
        nullable=False,
    )

    optimal_session_duration_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # "morning" / "afternoon" / "evening", inferred from historical
    # engagement-by-hour distribution.
    best_time_of_day: Mapped[str | None] = mapped_column(String(20), nullable=True)

    # How quickly difficulty should ramp: "slow" / "moderate" / "fast".
    preferred_difficulty_pace: Mapped[str | None] = mapped_column(String(20), nullable=True)

    attention_span_estimate_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Serialized (JSON string) vector describing learning style weights
    # e.g. {"visual": 0.6, "text": 0.3, "auditory": 0.1}. Kept as a
    # string here to stay portable between SQLite/Postgres without a
    # native JSON column dependency at this layer.
    learning_style_vector: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # Dropout/disengagement risk score, 0-100, from the early-warning model.
    risk_score: Mapped[float | None] = mapped_column(Float, nullable=True)

    student: Mapped["Student"] = relationship("Student", back_populates="learning_pattern")

    def __repr__(self) -> str:
        return f"<LearningPattern student_id={self.student_id}>"
