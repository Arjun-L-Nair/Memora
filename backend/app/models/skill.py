"""
models/skill.py

SQLAlchemy model for the `skills` table.

Skills are a predefined, teacher-independent practice library — separate
from teacher-authored LearningContent — organized into three tiers
(Easy / Medium / Hard) with a strict unlock gate: a student can attempt
a Medium-tier skill only once they've passed every Easy-tier skill, and
a Hard-tier skill only once they've passed every Medium-tier skill (see
services/skill_service.py for the unlock computation — this model only
stores the static skill definitions, never a student's progress).

Each Skill has 3 SkillExercises (see skill_exercise.py); passing a
skill means answering all 3 correctly across some attempt (not
necessarily the same attempt — see skill_service.py for the exact
"passed" definition).
"""

from __future__ import annotations

from sqlalchemy import Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base_model import BaseModel


class Skill(BaseModel):
    """A single predefined practice skill, belonging to one difficulty tier."""

    __tablename__ = "skills"

    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)

    # "Easy" | "Medium" | "Hard" — reuses the same three lower tiers of
    # the app's existing Beginner/Easy/Medium/Hard DIFFICULTY_ORDER
    # (Beginner is a LearningContent/Student adaptive-level concept
    # only; the skill library deliberately has just these 3 tiers).
    tier: Mapped[str] = mapped_column(String(10), nullable=False, index=True)

    # A short icon/category identifier for the student-facing skill
    # card (e.g. "pattern", "math", "shapes", "logic", "memory") — a
    # plain string rather than an enum so new categories don't need a
    # migration, purely presentational (maps to a lucide-react icon on
    # the frontend).
    category: Mapped[str] = mapped_column(String(30), nullable=False)

    # Fixed display/practice order within a tier.
    order_index: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    exercises: Mapped[list["SkillExercise"]] = relationship(
        "SkillExercise",
        back_populates="skill",
        cascade="all, delete-orphan",
        order_by="SkillExercise.order_index",
    )

    attempts: Mapped[list["SkillAttempt"]] = relationship(
        "SkillAttempt",
        back_populates="skill",
    )

    def __repr__(self) -> str:
        return f"<Skill id={self.id} name={self.name!r} tier={self.tier!r}>"
