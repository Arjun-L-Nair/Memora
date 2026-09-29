"""
models/plan_assignment.py

SQLAlchemy model for the `plan_assignments` table.

The source of truth for "which students is this LearningPlan currently
assigned to" — see learning_plan.py's module docstring for the
architecture context (this replaces the old one-student-per-plan
design, which forced a teacher to recreate an entire plan and its
content for every additional student).

A student can be assigned the same plan only once (unique constraint
on learning_plan_id + student_id) — assigning an already-assigned
student again is a no-op the service layer handles explicitly, not a
row this table would ever hold twice.
"""

from __future__ import annotations

from sqlalchemy import ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base_model import BaseModel


class PlanAssignment(BaseModel):
    """One (learning_plan, student) assignment pair."""

    __tablename__ = "plan_assignments"
    __table_args__ = (
        UniqueConstraint("learning_plan_id", "student_id", name="uq_plan_assignment_plan_student"),
    )

    learning_plan_id: Mapped[int] = mapped_column(
        ForeignKey("learning_plans.id"),
        index=True,
        nullable=False,
    )

    student_id: Mapped[int] = mapped_column(
        ForeignKey("students.id"),
        index=True,
        nullable=False,
    )

    learning_plan: Mapped["LearningPlan"] = relationship(
        "LearningPlan",
        back_populates="assignments",
    )

    student: Mapped["Student"] = relationship(
        "Student",
        back_populates="plan_assignments",
    )

    def __repr__(self) -> str:
        return f"<PlanAssignment plan_id={self.learning_plan_id} student_id={self.student_id}>"
