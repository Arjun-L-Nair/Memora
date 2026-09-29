"""
tests/test_migration_check.py

Covers database/migration_check.py: the read-only startup diagnostic
that warns if the connected database's Alembic revision is behind the
latest migration.

Isolation: uses a fully separate, throwaway SQLite file per test
(never the real backend/memora.db or the shared test fixture DB),
so these tests cannot interfere with or be interfered with by anything
else in the suite.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest
from sqlalchemy import create_engine

from app.database.migration_check import check_migrations_current


@pytest.fixture()
def scratch_db(tmp_path: Path) -> Path:
    """A throwaway SQLite file path, guaranteed not to exist yet."""
    return tmp_path / "scratch_migration_check.db"


def test_no_alembic_version_table_logs_info_not_warning(scratch_db, caplog):
    """
    A brand new database with no alembic_version table yet (i.e. never
    migrated) is a normal, expected state — not an error condition.
    Must log at INFO, never WARNING, and must never raise.
    """
    # Create an empty SQLite file with no tables at all.
    sqlite3.connect(scratch_db).close()

    engine = create_engine(f"sqlite:///{scratch_db}")

    import app.database.migration_check as module

    original_engine = module.engine
    module.engine = engine
    try:
        with caplog.at_level("INFO"):
            check_migrations_current()  # must not raise
    finally:
        module.engine = original_engine

    assert not any(r.levelname == "WARNING" for r in caplog.records)
    assert any("brand new database" in r.message for r in caplog.records)


def test_current_revision_matches_head_logs_info(scratch_db, caplog):
    """When the DB's stamped revision matches the latest migration, log
    an informational confirmation, not a warning."""
    from alembic.config import Config
    from alembic.script import ScriptDirectory

    engine = create_engine(f"sqlite:///{scratch_db}")
    with engine.connect() as conn:
        conn.exec_driver_sql(
            "CREATE TABLE alembic_version (version_num VARCHAR(32) NOT NULL)"
        )
        conn.commit()

    backend_dir = Path(__file__).resolve().parent.parent
    alembic_cfg = Config(str(backend_dir / "alembic.ini"))
    script_dir = ScriptDirectory.from_config(alembic_cfg)
    latest = script_dir.get_current_head()

    with engine.connect() as conn:
        conn.exec_driver_sql(
            "INSERT INTO alembic_version (version_num) VALUES (:v)",
            {"v": latest},
        )
        conn.commit()

    import app.database.migration_check as module

    original_engine = module.engine
    module.engine = engine
    try:
        with caplog.at_level("INFO"):
            check_migrations_current()
    finally:
        module.engine = original_engine

    assert not any(r.levelname == "WARNING" for r in caplog.records)
    assert any("up to date" in r.message for r in caplog.records)


def test_stale_revision_logs_clear_warning_with_fix_instructions(scratch_db, caplog):
    """
    The primary case this module exists for: a database stamped at an
    OLDER revision than the latest available migration must produce a
    single, clear WARNING naming both revisions and the exact fix
    command — this is the diagnostic that would have caught the
    "empty analytics after a rerun" symptom immediately at startup.
    """
    engine = create_engine(f"sqlite:///{scratch_db}")
    with engine.connect() as conn:
        conn.exec_driver_sql(
            "CREATE TABLE alembic_version (version_num VARCHAR(32) NOT NULL)"
        )
        conn.exec_driver_sql(
            "INSERT INTO alembic_version (version_num) VALUES ('a66eb33521d9')"
        )
        conn.commit()

    import app.database.migration_check as module

    original_engine = module.engine
    module.engine = engine
    try:
        with caplog.at_level("WARNING"):
            check_migrations_current()  # must not raise even though schema is stale
    finally:
        module.engine = original_engine

    warnings = [r for r in caplog.records if r.levelname == "WARNING"]
    assert len(warnings) == 1
    assert "OUT OF DATE" in warnings[0].message
    assert "a66eb33521d9" in warnings[0].message
    assert "alembic upgrade head" in warnings[0].message


def test_check_never_raises_even_on_unexpected_db_error():
    """
    This is a diagnostic-only check — it must never be capable of
    crashing application startup, even if the database connection
    itself is completely broken.
    """
    from sqlalchemy import create_engine as _create_engine

    broken_engine = _create_engine("sqlite:////nonexistent/path/that/cannot/work.db")

    import app.database.migration_check as module

    original_engine = module.engine
    module.engine = broken_engine
    try:
        check_migrations_current()  # must not raise
    finally:
        module.engine = original_engine
