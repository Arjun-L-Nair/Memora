"""plan reuse restructure (nullable learning_plans.student_id + plan_assignments) and skills library

Revision ID: 8a3f4c9d1e02
Revises: 6e056c6903ef
Create Date: 2026-09-19 00:00:00.000000

Two independent changes bundled in one migration since both were
designed and reviewed together:

1. Plan-reuse restructure (see models/learning_plan.py and
   models/plan_assignment.py module docstrings for the full
   rationale): learning_plans.student_id becomes NULLABLE, and a new
   plan_assignments join table becomes the actual source of truth for
   "which students is this plan assigned to." Every existing plan's
   student_id is backfilled into a corresponding plan_assignments row
   so no existing assignment relationship is lost — student_id itself
   is left in place (not dropped) for backward compatibility, per the
   model's own documented legacy-fallback behavior.

2. Skills library: skills, skill_exercises, skill_attempts — a
   predefined, teacher-independent practice library, unrelated to
   LearningPlan/LearningContent. See models/skill.py.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "8a3f4c9d1e02"
down_revision: Union[str, Sequence[str], None] = "6e056c6903ef"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # --- 1a. learning_plans.student_id -> nullable ---
    # batch_alter_table is required for SQLite (which can't ALTER
    # COLUMN in place); it's a no-op wrapper on Postgres.
    with op.batch_alter_table("learning_plans") as batch_op:
        batch_op.alter_column(
            "student_id",
            existing_type=sa.Integer(),
            nullable=True,
        )

    # --- 1b. plan_assignments ---
    op.create_table(
        "plan_assignments",
        sa.Column("learning_plan_id", sa.Integer(), nullable=False),
        sa.Column("student_id", sa.Integer(), nullable=False),
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["learning_plan_id"], ["learning_plans.id"]),
        sa.ForeignKeyConstraint(["student_id"], ["students.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("learning_plan_id", "student_id", name="uq_plan_assignment_plan_student"),
    )
    op.create_index(op.f("ix_plan_assignments_learning_plan_id"), "plan_assignments", ["learning_plan_id"])
    op.create_index(op.f("ix_plan_assignments_student_id"), "plan_assignments", ["student_id"])

    # --- 1c. Backfill: one plan_assignments row per existing (plan, student) pair ---
    op.execute(
        """
        INSERT INTO plan_assignments (learning_plan_id, student_id, created_at, updated_at)
        SELECT id, student_id, created_at, updated_at
        FROM learning_plans
        WHERE student_id IS NOT NULL
        """
    )

    # --- 2. Skills library ---
    op.create_table(
        "skills",
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("tier", sa.String(length=10), nullable=False),
        sa.Column("category", sa.String(length=30), nullable=False),
        sa.Column("order_index", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_skills_tier"), "skills", ["tier"])

    op.create_table(
        "skill_exercises",
        sa.Column("skill_id", sa.Integer(), nullable=False),
        sa.Column("prompt", sa.Text(), nullable=False),
        sa.Column("options_json", sa.Text(), nullable=False),
        sa.Column("correct_option_index", sa.Integer(), nullable=False),
        sa.Column("order_index", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["skill_id"], ["skills.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_skill_exercises_skill_id"), "skill_exercises", ["skill_id"])

    op.create_table(
        "skill_attempts",
        sa.Column("student_id", sa.Integer(), nullable=False),
        sa.Column("skill_id", sa.Integer(), nullable=False),
        sa.Column("skill_exercise_id", sa.Integer(), nullable=False),
        sa.Column("selected_option_index", sa.Integer(), nullable=False),
        sa.Column("is_correct", sa.Boolean(), nullable=False),
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["student_id"], ["students.id"]),
        sa.ForeignKeyConstraint(["skill_id"], ["skills.id"]),
        sa.ForeignKeyConstraint(["skill_exercise_id"], ["skill_exercises.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_skill_attempts_student_id"), "skill_attempts", ["student_id"])
    op.create_index(op.f("ix_skill_attempts_skill_id"), "skill_attempts", ["skill_id"])
    op.create_index(op.f("ix_skill_attempts_skill_exercise_id"), "skill_attempts", ["skill_exercise_id"])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f("ix_skill_attempts_skill_exercise_id"), table_name="skill_attempts")
    op.drop_index(op.f("ix_skill_attempts_skill_id"), table_name="skill_attempts")
    op.drop_index(op.f("ix_skill_attempts_student_id"), table_name="skill_attempts")
    op.drop_table("skill_attempts")

    op.drop_index(op.f("ix_skill_exercises_skill_id"), table_name="skill_exercises")
    op.drop_table("skill_exercises")

    op.drop_index(op.f("ix_skills_tier"), table_name="skills")
    op.drop_table("skills")

    op.drop_index(op.f("ix_plan_assignments_student_id"), table_name="plan_assignments")
    op.drop_index(op.f("ix_plan_assignments_learning_plan_id"), table_name="plan_assignments")
    op.drop_table("plan_assignments")

    with op.batch_alter_table("learning_plans") as batch_op:
        batch_op.alter_column(
            "student_id",
            existing_type=sa.Integer(),
            nullable=False,
        )
