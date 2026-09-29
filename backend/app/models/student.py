"""
models/student.py

SQLAlchemy model for the `students` table.

Students authenticate via Student ID + 4-digit PIN (no email/password),
per Master Specification Section 6. Teachers create student accounts;
students cannot self-register.

Relationship notes:
    - Student -> Teacher: many-to-one (owning teacher). NO cascade delete
      configured on this side (mirrors Teacher's decision).
    - Student -> LearningPlan: one-to-many. NO cascade delete — this
      project follows a soft-delete philosophy (accounts are deactivated
      via is_active, never hard-deleted), so educational history must
      persist regardless of account lifecycle.
    - Student -> LearningSession: one-to-many. Same reasoning as above.
"""

from __future__ import annotations

from sqlalchemy import Boolean, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import true

from app.models.base_model import BaseModel


class Student(BaseModel):
    """
    Represents a student account.

    Inherits `id`, `created_at`, `updated_at` from BaseModel.
    """

    __tablename__ = "students"

    # The human-facing login identifier (the "Student ID" used at login).
    student_code: Mapped[str] = mapped_column(
        String(20),
        unique=True,
        index=True,
        nullable=False,
    )

    full_name: Mapped[str] = mapped_column(String(100), nullable=False)

    # Hashed 4-digit PIN. Never stored as plaintext.
    pin_hash: Mapped[str] = mapped_column(String(255), nullable=False)

    # Owning teacher. Indexed since it's used for teacher -> students lookups.
    teacher_id: Mapped[int] = mapped_column(
        ForeignKey("teachers.id"),
        index=True,
        nullable=False,
    )

    # Student's current adaptive learning level, cached to avoid
    # recalculating it on every login. Validated in the app layer:
    # Beginner / Easy / Medium / Hard.
    current_difficulty_level: Mapped[str] = mapped_column(
        String(20),
        default="Beginner",
        server_default="Beginner",
        nullable=False,
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        server_default=true(),
        nullable=False,
    )

    # --- Relationships ---

    # The teacher who created/owns this student.
    teacher: Mapped["Teacher"] = relationship(
        "Teacher",
        back_populates="students",
    )

    # Learning plans assigned to this student. NO cascade delete: this
    # project follows a soft-delete philosophy — students are deactivated,
    # not deleted, so educational history must never be silently removed.
    # LEGACY relationship, via LearningPlan.student_id — see that model's
    # module docstring. Use plan_assignments for the current set of plans
    # actually assigned to this student.
    learning_plans: Mapped[list["LearningPlan"]] = relationship(
        "LearningPlan",
        back_populates="student",
    )

    # Which LearningPlans this student is currently assigned, via
    # PlanAssignment — the source of truth post plan-reuse-restructure.
    plan_assignments: Mapped[list["PlanAssignment"]] = relationship(
        "PlanAssignment",
        back_populates="student",
    )

    # Skill-practice attempt history (see models/skill_attempt.py) —
    # "has this student passed skill X" is computed from these, not
    # stored separately.
    skill_attempts: Mapped[list["SkillAttempt"]] = relationship(
        "SkillAttempt",
        back_populates="student",
    )

    # Learning sessions belonging to this student. Same reasoning as above.
    learning_sessions: Mapped[list["LearningSession"]] = relationship(
        "LearningSession",
        back_populates="student",
    )

    # One-to-one sensory/cognitive-load preferences (see sensory_profile.py).
    sensory_profile: Mapped["SensoryProfile | None"] = relationship(
        "SensoryProfile",
        back_populates="student",
        uselist=False,
    )

    # Mira companion chat log, oldest-first. See conversation_history.py.
    conversation_history: Mapped[list["ConversationHistory"]] = relationship(
        "ConversationHistory",
        back_populates="student",
    )

    # Point-in-time emotion readings. See emotion_log.py.
    emotion_logs: Mapped[list["EmotionLog"]] = relationship(
        "EmotionLog",
        back_populates="student",
    )

    # ML-inferred behavioral pattern (one row, recomputed periodically).
    # See learning_pattern.py.
    learning_pattern: Mapped["LearningPattern | None"] = relationship(
        "LearningPattern",
        back_populates="student",
        uselist=False,
    )

    def __repr__(self) -> str:
        """Developer-friendly representation, useful for debugging/logging."""
        return f"<Student id={self.id} student_code={self.student_code!r}>"
