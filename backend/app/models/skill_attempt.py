"""
models/skill_attempt.py

SQLAlchemy model for the `skill_attempts` table — one student's answer
to one SkillExercise. A student may attempt the same exercise more
than once (no uniqueness constraint); "has the student passed this
skill" is computed from these rows by services/skill_service.py
(their most recent attempt per exercise, all 3 correct), not stored as
a separate denormalized progress flag — a single source of truth
avoids any risk of a stored "completed" flag drifting out of sync with
the actual attempt history.
"""

from __future__ import annotations

from sqlalchemy import Boolean, ForeignKey, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base_model import BaseModel


class SkillAttempt(BaseModel):
    """One student's answer to one skill exercise."""

    __tablename__ = "skill_attempts"

    student_id: Mapped[int] = mapped_column(ForeignKey("students.id"), index=True, nullable=False)
    skill_id: Mapped[int] = mapped_column(ForeignKey("skills.id"), index=True, nullable=False)
    skill_exercise_id: Mapped[int] = mapped_column(ForeignKey("skill_exercises.id"), index=True, nullable=False)

    selected_option_index: Mapped[int] = mapped_column(Integer, nullable=False)
    is_correct: Mapped[bool] = mapped_column(Boolean, nullable=False)

    student: Mapped["Student"] = relationship("Student", back_populates="skill_attempts")
    skill: Mapped["Skill"] = relationship("Skill", back_populates="attempts")

    def __repr__(self) -> str:
        return f"<SkillAttempt student_id={self.student_id} exercise_id={self.skill_exercise_id} correct={self.is_correct}>"
