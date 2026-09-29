"""
database/migration_check.py

Startup safety check: warns loudly if the connected database's Alembic
revision is behind the latest migration defined in alembic/versions/.

Why this exists:
    `init_db()` (database/init_db.py) calls `Base.metadata.create_all()`,
    which only CREATES tables that don't exist yet — it is a complete
    no-op for tables that already exist, even if their schema is
    missing columns added by a newer Alembic migration (for example,
    the video_url/teacher_notes columns added to learning_contents
    after the initial schema). This means a stale database can start
    the app successfully, with no error at startup, and only fail
    later with a confusing SQL error the first time code touches a
    missing column — or worse, simply behave as if features involving
    that column don't exist, with no error at all.

    This check runs a lightweight, read-only query against the
    database's own alembic_version table (which Alembic itself
    maintains) and compares it to the latest revision Alembic knows
    about from the versions/ directory. It cannot fix a stale schema
    automatically — only `alembic upgrade head`, run from the backend/
    directory, can safely apply the missing migration(s) — but it
    guarantees the mismatch is loud and immediate at startup instead
    of silent and delayed.

Safe by design:
    This module never modifies the database. It only reads the
    alembic_version table if present, and never raises — a failure to
    determine migration status (e.g. a brand new database with no
    alembic_version table yet) is logged as informational, not treated
    as an error, since `alembic upgrade head` on a fresh database is
    the normal first-time setup path.
"""

from __future__ import annotations

import logging

from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import inspect, text

from app.database.session import engine

logger = logging.getLogger("memora")


def check_migrations_current() -> None:
    """
    Compare the database's current Alembic revision against the latest
    revision available in alembic/versions/, and log a clear, actionable
    WARNING if they differ. Never raises — this is a diagnostic aid,
    not a hard startup gate, so a misconfigured Alembic setup can never
    itself prevent the application from starting.
    """
    try:
        inspector = inspect(engine)
        if "alembic_version" not in inspector.get_table_names():
            logger.info(
                "No alembic_version table found yet — this looks like a "
                "brand new database. Run 'alembic upgrade head' from the "
                "backend/ directory to create the schema."
            )
            return

        with engine.connect() as conn:
            result = conn.execute(text("SELECT version_num FROM alembic_version"))
            row = result.fetchone()
            current_revision = row[0] if row else None

        # Resolve the latest revision Alembic knows about from the
        # versions/ directory itself, using the same alembic.ini this
        # project's CLI commands already use — so this check is always
        # comparing against the exact same "head" that
        # `alembic upgrade head` would target.
        from pathlib import Path

        alembic_ini_path = Path(__file__).resolve().parent.parent.parent / "alembic.ini"
        alembic_cfg = Config(str(alembic_ini_path))
        script_dir = ScriptDirectory.from_config(alembic_cfg)
        latest_revision = script_dir.get_current_head()

        if current_revision == latest_revision:
            logger.info(
                "Database schema is up to date (revision %s).", current_revision
            )
        else:
            logger.warning(
                "DATABASE SCHEMA IS OUT OF DATE. Current revision: %s | "
                "Latest available revision: %s. The application will "
                "still start, but any feature relying on columns/tables "
                "added by a newer migration may behave incorrectly or "
                "fail unexpectedly. Fix this by running, from the "
                "backend/ directory: alembic upgrade head",
                current_revision,
                latest_revision,
            )
    except Exception as exc:  # noqa: BLE001 - diagnostic only, must never crash startup
        logger.info(
            "Could not determine migration status (this is informational, "
            "not an error): %s",
            exc,
        )
