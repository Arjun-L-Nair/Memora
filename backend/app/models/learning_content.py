"""
models/learning_content.py

SQLAlchemy model for the `learning_contents` table.

LearningContent represents the actual instructional material (lessons,
explanations, quiz source material) used within a LearningPlan. Content
can be adapted in complexity based on engagement prediction, and is
reusable across sessions (see Master Specification, Section 10).

Relationship notes:
    - LearningContent -> LearningPlan: many-to-one (owning plan).
    - LearningContent -> LearningSession: one-to-many. NO cascade delete —
      sessions are historical/analytics records and must persist even if
      the content used is later deactivated or removed.
"""

from __future__ import annotations

from sqlalchemy import Boolean, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import true

from app.models.base_model import BaseModel


class LearningContent(BaseModel):
    """
    Represents a single piece of instructional material belonging to a
    LearningPlan.

    Inherits `id`, `created_at`, `updated_at` from BaseModel.
    """

    __tablename__ = "learning_contents"

    title: Mapped[str] = mapped_column(String(150), nullable=False)

    # Subject area, e.g. "Math", "Reading". Optional.
    subject: Mapped[str | None] = mapped_column(String(100), nullable=True)

    # Core instructional content/explanation shown to the student.
    body: Mapped[str] = mapped_column(Text, nullable=False)

    # Optional URL of an instructional video (YouTube embed or direct MP4).
    # NULL means no video is attached to this content.
    video_url: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # Optional supplementary notes from the teacher, shown below the main
    # content body on the student's Learning page.
    teacher_notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Content difficulty level, validated in the app layer.
    difficulty_level: Mapped[str] = mapped_column(String(20), nullable=False)

    # Owning learning plan. Indexed for fast "content within plan X" lookups.
    learning_plan_id: Mapped[int] = mapped_column(
        ForeignKey("learning_plans.id"),
        index=True,
        nullable=False,
    )

    # Lets teachers temporarily disable a lesson without deleting it.
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        server_default=true(),
        nullable=False,
    )

    # --- Relationships ---

    # The plan this content belongs to.
    learning_plan: Mapped["LearningPlan"] = relationship(
        "LearningPlan",
        back_populates="learning_contents",
    )

    # Sessions in which this content was used. NO cascade delete — sessions
    # are historical/analytics records that must persist regardless of the
    # content's lifecycle.
    learning_sessions: Mapped[list["LearningSession"]] = relationship(
        "LearningSession",
        back_populates="learning_content",
    )

    def __repr__(self) -> str:
        """Developer-friendly representation, useful for debugging/logging."""
        return f"<LearningContent id={self.id} title={self.title!r}>"
