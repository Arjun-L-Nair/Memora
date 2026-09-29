"""
models/skill_exercise.py

SQLAlchemy model for the `skill_exercises` table — one multiple-choice
question belonging to a Skill. Each Skill has a fixed set of 3
exercises, seeded once (see database/seed_skills.py) rather than
generated — deliberately NOT AI-generated like quiz questions, since
the skill library is meant to be a small, hand-curated, predictable
practice set (consistent with the project's broader "predictability
over novelty" design philosophy for autistic learners), not a
constantly-changing pool.
"""

from __future__ import annotations

from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship


from app.models.base_model import BaseModel


class SkillExercise(BaseModel):
    """One multiple-choice question within a Skill."""

    __tablename__ = "skill_exercises"

    skill_id: Mapped[int] = mapped_column(ForeignKey("skills.id"), index=True, nullable=False)

    prompt: Mapped[str] = mapped_column(Text, nullable=False)

    # Stored as a JSON-encoded list[str] (same pattern as
    # QuizAttempt.questions_json elsewhere in this codebase) rather
    # than a separate options table — a fixed, small (2-4 item) list
    # that's always read/written as a whole, never queried per-option.
    options_json: Mapped[str] = mapped_column(Text, nullable=False)

    correct_option_index: Mapped[int] = mapped_column(Integer, nullable=False)

    order_index: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    skill: Mapped["Skill"] = relationship("Skill", back_populates="exercises")

    def __repr__(self) -> str:
        return f"<SkillExercise id={self.id} skill_id={self.skill_id}>"
