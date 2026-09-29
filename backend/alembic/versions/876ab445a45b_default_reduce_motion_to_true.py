"""default reduce_motion to true

Revision ID: 876ab445a45b
Revises: 8a3f4c9d1e02
Create Date: 2026-09-29 00:00:00.000000

Changes the default for sensory_profiles.reduce_motion from False to
True, for newly-created profiles. Does not alter existing students'
saved preference (see the optional backfill UPDATE below, commented
out by default).

SQLite cannot run a plain `ALTER TABLE ... ALTER COLUMN ... SET
DEFAULT` (that's Postgres/MySQL syntax) — batch_alter_table is
required, same as the nullable change in 8a3f4c9d1e02. On SQLite this
recreates the table under the hood; batch_alter_table is a no-op
wrapper on Postgres, so this stays portable.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "876ab445a45b"
down_revision: Union[str, Sequence[str], None] = "8a3f4c9d1e02"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("sensory_profiles") as batch_op:
        batch_op.alter_column(
            "reduce_motion",
            existing_type=sa.Boolean(),
            server_default=sa.text("true"),
            existing_nullable=False,
        )

    # Uncomment to also switch existing students over, not just new
    # profiles created from now on:
    # op.execute("UPDATE sensory_profiles SET reduce_motion = 1")


def downgrade() -> None:
    with op.batch_alter_table("sensory_profiles") as batch_op:
        batch_op.alter_column(
            "reduce_motion",
            existing_type=sa.Boolean(),
            server_default=sa.text("false"),
            existing_nullable=False,
        )
