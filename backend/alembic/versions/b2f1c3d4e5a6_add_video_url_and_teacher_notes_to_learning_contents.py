"""add video_url and teacher_notes to learning_contents

Revision ID: b2f1c3d4e5a6
Revises: a66eb33521d9
Create Date: 2025-01-01 00:00:00.000000

Adds two optional columns to learning_contents:
  - video_url:      URL of an optional instructional video (YouTube embed
                    or direct MP4). NULL = no video attached.
  - teacher_notes:  Private/supplementary notes from the teacher shown
                    below the main content body. NULL = no notes.

Both columns are nullable with no server_default so existing rows get
NULL without a table rewrite, which is safe for SQLite.
"""

from alembic import op
import sqlalchemy as sa

revision = "b2f1c3d4e5a6"
down_revision = "a66eb33521d9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "learning_contents",
        sa.Column("video_url", sa.String(length=500), nullable=True),
    )
    op.add_column(
        "learning_contents",
        sa.Column("teacher_notes", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("learning_contents", "teacher_notes")
    op.drop_column("learning_contents", "video_url")
