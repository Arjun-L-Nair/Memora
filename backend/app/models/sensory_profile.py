"""
models/sensory_profile.py

SQLAlchemy model for the `sensory_profiles` table.

Stores a student's sensory and cognitive-load preferences so the UI and
the learning companion (Mira) can adapt presentation to reduce sensory
overwhelm — a core requirement for an autism-optimized experience.

One-to-one with Student: each student has exactly one profile, created
with sensible defaults on first login and editable thereafter (by the
student or their teacher).
"""

from __future__ import annotations

from sqlalchemy import Boolean, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base_model import BaseModel


class SensoryProfile(BaseModel):
    """Per-student sensory and cognitive-load preferences."""

    __tablename__ = "sensory_profiles"

    student_id: Mapped[int] = mapped_column(
        ForeignKey("students.id"),
        unique=True,
        index=True,
        nullable=False,
    )

    # Preferred input/output modality: visual / auditory / text / mixed.
    preferred_mode: Mapped[str] = mapped_column(
        String(20),
        default="mixed",
        server_default="mixed",
        nullable=False,
    )

    # 0.0 (low sensitivity) - 1.0 (high sensitivity). Drives animation
    # intensity, color contrast, and sound defaults.
    sensory_sensitivity_score: Mapped[float] = mapped_column(
        Float,
        default=0.5,
        server_default="0.5",
        nullable=False,
    )

    reduce_motion: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true", nullable=False)
    high_contrast: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false", nullable=False)
    mute_sounds: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false", nullable=False)

    # Font choice for dyslexia/readability support (e.g. "default", "opendyslexic").
    font_preference: Mapped[str] = mapped_column(
        String(30),
        default="default",
        server_default="default",
        nullable=False,
    )

    # Estimated comfortable session length in minutes; feeds the adaptive
    # engine's session-length suggestions.
    attention_span_minutes: Mapped[int] = mapped_column(
        Integer,
        default=15,
        server_default="15",
        nullable=False,
    )

    student: Mapped["Student"] = relationship("Student", back_populates="sensory_profile")

    def __repr__(self) -> str:
        return f"<SensoryProfile student_id={self.student_id}>"
