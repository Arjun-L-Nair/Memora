"""add sensory_profile, conversation_history, emotion_log, learning_pattern

Revision ID: 6e056c6903ef
Revises: b2f1c3d4e5a6
Create Date: 2026-09-12 00:00:00.000000

Part of the Memora overhaul (see implementation_plan.md, Components 1-3).
Adds four new tables supporting autism-specific personalization:

  - sensory_profiles:     one-to-one per-student sensory/UI preferences.
  - conversation_history: persistent Mira chat log (student + mira turns).
  - emotion_logs:         point-in-time emotion readings (check-in/chat/reflection).
  - learning_patterns:    one-to-one ML-inferred behavioral pattern per student.

This project has chosen a fresh-database reset alongside this migration
(rather than a data-preserving upgrade), so no data backfill logic is
included here — `alembic upgrade head` against an empty database creates
the complete current schema in one pass.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "6e056c6903ef"
down_revision: Union[str, Sequence[str], None] = "b2f1c3d4e5a6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "sensory_profiles",
        sa.Column("student_id", sa.Integer(), nullable=False),
        sa.Column("preferred_mode", sa.String(length=20), server_default="mixed", nullable=False),
        sa.Column("sensory_sensitivity_score", sa.Float(), server_default="0.5", nullable=False),
        sa.Column("reduce_motion", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("high_contrast", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("mute_sounds", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("font_preference", sa.String(length=30), server_default="default", nullable=False),
        sa.Column("attention_span_minutes", sa.Integer(), server_default="15", nullable=False),
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["student_id"], ["students.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_sensory_profiles_student_id"), "sensory_profiles", ["student_id"], unique=True)

    op.create_table(
        "conversation_history",
        sa.Column("student_id", sa.Integer(), nullable=False),
        sa.Column("role", sa.String(length=10), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("emotion_detected", sa.String(length=20), nullable=True),
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["student_id"], ["students.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_conversation_history_student_id"), "conversation_history", ["student_id"], unique=False)

    op.create_table(
        "emotion_logs",
        sa.Column("student_id", sa.Integer(), nullable=False),
        sa.Column("emotion", sa.String(length=20), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("source", sa.String(length=20), nullable=False),
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["student_id"], ["students.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_emotion_logs_student_id"), "emotion_logs", ["student_id"], unique=False)

    op.create_table(
        "learning_patterns",
        sa.Column("student_id", sa.Integer(), nullable=False),
        sa.Column("optimal_session_duration_minutes", sa.Integer(), nullable=True),
        sa.Column("best_time_of_day", sa.String(length=20), nullable=True),
        sa.Column("preferred_difficulty_pace", sa.String(length=20), nullable=True),
        sa.Column("attention_span_estimate_minutes", sa.Integer(), nullable=True),
        sa.Column("learning_style_vector", sa.String(length=500), nullable=True),
        sa.Column("risk_score", sa.Float(), nullable=True),
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["student_id"], ["students.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_learning_patterns_student_id"), "learning_patterns", ["student_id"], unique=True)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f("ix_learning_patterns_student_id"), table_name="learning_patterns")
    op.drop_table("learning_patterns")
    op.drop_index(op.f("ix_emotion_logs_student_id"), table_name="emotion_logs")
    op.drop_table("emotion_logs")
    op.drop_index(op.f("ix_conversation_history_student_id"), table_name="conversation_history")
    op.drop_table("conversation_history")
    op.drop_index(op.f("ix_sensory_profiles_student_id"), table_name="sensory_profiles")
    op.drop_table("sensory_profiles")
