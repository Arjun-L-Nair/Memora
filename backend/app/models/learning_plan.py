"""
models/learning_plan.py

SQLAlchemy model for the `learning_plans` table.

A LearningPlan represents a reusable container of LearningContent,
created by a teacher and assignable to any number of students from
her own roster — see models/plan_assignment.py for the join table
that expresses "which students is this plan currently assigned to."

Architecture note (plan-reuse restructure):
    Originally a LearningPlan belonged to exactly one student
    (student_id was NOT NULL). That meant assigning the same lesson
    to five students required recreating the entire plan and its
    content five times. student_id is now NULLABLE and kept only for
    backward compatibility with data created before this change — new
    plans are created with student_id=NULL and assigned to students
    via PlanAssignment rows instead, which is what every ownership/
    ory recommendation check in the codebase now actually reads.
    Existing pre-restructure plans work unchanged: the migration
    backfills a PlanAssignment row for each one from its old
    student_id, and code that still checks student_id as a legacy
    fallback continues to work for any row where it's still set.

Relationship notes:
    - LearningPlan -> Teacher: many-to-one (owning teacher).
    - LearningPlan -> Student (student_id): many-to-one, NULLABLE,
      legacy-only — see above. Do not use this to determine which
      students a plan is assigned to; use `assignments` instead.
    - LearningPlan -> PlanAssignment: one-to-many, cascade
      delete-orphan — assignment rows are pure join data owned by the
      plan.
    - LearningPlan -> LearningContent: one-to-many, cascade delete-orphan.
      Content is organizational data owned directly by its plan, so it is
      cleaned up when the plan itself is deleted.
    - LearningPlan -> LearningSession: one-to-many. NO cascade delete —
      sessions are historical/analytics records and must persist under
      this project's soft-delete philosophy.
"""

from __future__ import annotations

from sqlalchemy import Boolean, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import true

from app.models.base_model import BaseModel


class LearningPlan(BaseModel):
    """
    A reusable container of learning content, owned by a teacher and
    assignable to any number of her students (see PlanAssignment).

    Inherits `id`, `created_at`, `updated_at` from BaseModel.
    """

    __tablename__ = "learning_plans"

    title: Mapped[str] = mapped_column(String(150), nullable=False)

    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # LEGACY / backward-compat only. Do not use to determine which
    # students this plan is assigned to — read `assignments` (via
    # PlanAssignment) instead. Nullable because new plans are created
    # unassigned (student_id=NULL) and assigned afterward through
    # PlanAssignment rows; this column only still has a value for
    # plans created before the plan-reuse restructure, or wherever a
    # single-student-plan creation path deliberately sets it for
    # backward compatibility. See this file's module docstring.
    student_id: Mapped[int | None] = mapped_column(
        ForeignKey("students.id"),
        index=True,
        nullable=True,
    )

    # The teacher who created/owns this plan. Indexed for fast lookups
    # of "all plans created by teacher X".
    teacher_id: Mapped[int] = mapped_column(
        ForeignKey("teachers.id"),
        index=True,
        nullable=False,
    )

    # Estimated time to complete the plan, for teacher planning/scheduling.
    estimated_duration_minutes: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        server_default=true(),
        nullable=False,
    )

    # --- Relationships ---

    # LEGACY single-student relationship — see student_id's own comment.
    student: Mapped["Student | None"] = relationship(
        "Student",
        back_populates="learning_plans",
    )

    # The teacher who created this plan.
    teacher: Mapped["Teacher"] = relationship(
        "Teacher",
        back_populates="learning_plans",
    )

    # Which students this plan is CURRENTLY assigned to — the actual
    # source of truth post-restructure, read by every ownership/
    # recommendation check. See models/plan_assignment.py.
    assignments: Mapped[list["PlanAssignment"]] = relationship(
        "PlanAssignment",
        back_populates="learning_plan",
        cascade="all, delete-orphan",
    )

    # Instructional content belonging to this plan. Content is owned
    # directly by its plan, so it is removed along with the plan.
    learning_contents: Mapped[list["LearningContent"]] = relationship(
        "LearningContent",
        back_populates="learning_plan",
        cascade="all, delete-orphan",
    )

    # Sessions grouped under this plan. NO cascade delete — sessions are
    # historical/analytics records that must persist (soft-delete philosophy).
    learning_sessions: Mapped[list["LearningSession"]] = relationship(
        "LearningSession",
        back_populates="learning_plan",
    )

    def __repr__(self) -> str:
        """Developer-friendly representation, useful for debugging/logging."""
        return f"<LearningPlan id={self.id} title={self.title!r}>"
