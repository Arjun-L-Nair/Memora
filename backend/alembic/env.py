"""
alembic/env.py

Alembic migration environment script.

This is the script Alembic actually executes for every migration command
(`alembic revision --autogenerate`, `alembic upgrade head`, etc.). Two
things make it work correctly with this project's frozen database layer:

1. `target_metadata` is set to `Base.metadata`, imported from `app.models`
   (not `app.database.base` directly). `app/models/__init__.py` (frozen,
   Phase 2) imports every one of the 9 domain models in dependency order
   specifically so SQLAlchemy's mapper registry sees all of them before
   any `relationship()` string reference is resolved. Importing `Base`
   through `app.models` here guarantees Alembic's autogenerate sees the
   COMPLETE schema — all 9 tables, all foreign keys, all indexes — not
   an empty or partial `metadata` object.

2. The actual database connection URL is taken from
   `app.core.config.settings.DATABASE_URL` at runtime, overriding
   whatever is (or isn't) set in `alembic.ini`. This means there is only
   ONE source of truth for the connection string across the whole
   application — the same `.env`-driven `settings` object that
   `database/session.py` uses. Switching from SQLite to PostgreSQL later
   requires changing only the `.env` file; this script needs no edits.
"""

from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool

from alembic import context

# --- Import the frozen application configuration and models ---
#
# Import order matters here. `app.database` (frozen, Module 5) imports
# `app.database.init_db`, which itself imports `from app.models import
# Base`. `app.models` (frozen) in turn imports `from app.database.base
# import Base` as its very first statement. This is a real circular
# dependency between the two packages, but it is order-dependent: it
# only fails if `app.models` starts importing BEFORE `app.database` has
# begun initializing. Importing `app.database` first here (exactly as
# `main.py` already does) ensures `app.models` gets fully initialized
# as a side effect of `app.database`'s own import chain, avoiding the
# failure. This is a property of how the two frozen packages already
# depend on each other — nothing in either package was changed to
# achieve this; only the order of imports in this script matters.
#
# NOTE: `app.database` is imported here ONLY to force this safe import
# order (see above). Alembic constructs its OWN Engine below via
# `engine_from_config()`, per Alembic's own recommended architecture —
# see the design note above `run_migrations_online()` for why this is
# correct and not a duplicate-engine problem.
from app.core.config import settings
from app.database import engine as _app_engine  # noqa: F401  (import order only; not used directly)
from app.models import Base

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Override the connection URL from alembic.ini with the application's
# single source of truth: settings.DATABASE_URL. This keeps the database
# connection string defined in exactly one place (the .env file / Settings
# class), rather than duplicated between alembic.ini and the app itself.
config.set_main_option("sqlalchemy.url", settings.DATABASE_URL)

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# The complete, frozen ORM metadata — this is what enables
# `alembic revision --autogenerate` to detect the full schema
# (all 9 tables, foreign keys, indexes) defined in app/models/.
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.
    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine and associate a
    connection with the context.

    This deliberately constructs its OWN Engine via
    `engine_from_config()`, per Alembic's officially documented and
    scaffolded pattern (this is what `alembic init` generates by
    default, and what Alembic's own tutorial/cookbook examples use).

    Why this is NOT a duplicate-engine architectural problem:
    Alembic runs as a separate, short-lived CLI process — it is never
    running concurrently with the FastAPI application in the same
    process. The "no duplicate engine" principle in
    `database/__init__.py` (Module 5) exists to prevent two independent,
    long-lived connection pools serving live application traffic within
    the SAME process, which could cause transaction-visibility
    inconsistencies. That risk does not apply here. Additionally,
    `poolclass=pool.NullPool` deliberately disables real connection
    pooling for this Engine — it opens one connection, uses it for the
    migration, and discards it — which is the correct behavior for a
    one-shot script and is a poor fit for the app's long-lived, pooled
    `engine` object. Using two Engines with two different, appropriate
    lifetimes (long-lived pooled engine for the app; short-lived
    unpooled engine for migrations) is intentional, not accidental
    duplication.

    `settings.DATABASE_URL` remains the single source of truth for the
    connection string in both cases: it was written into
    `config`'s "sqlalchemy.url" option above, and `engine_from_config()`
    reads that exact value.
    """
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection, target_metadata=target_metadata
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
