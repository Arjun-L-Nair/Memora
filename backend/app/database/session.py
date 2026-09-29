"""
database/session.py

Database connection and session management.

This module is responsible for RUNTIME database connectivity — creating
the SQLAlchemy Engine, the Session factory, and the FastAPI dependency
used to hand a database session to routers/services on a per-request
basis.

This is distinct from `app/models/`, which only describes table
structure, and has no knowledge of *how* the application connects to
the database at runtime.

Design notes:
    - The connection string (DATABASE_URL) is read from app.core.config,
      which loads it from environment variables / .env. This file itself
      contains no hardcoded credentials or paths.
    - SQLite requires `connect_args={"check_same_thread": False}` because
      SQLite connections are, by default, restricted to the thread that
      created them. FastAPI may serve a request on a different thread
      than the one that opened the connection, so this flag is required
      for SQLite specifically. It is skipped for other database engines
      (e.g. PostgreSQL) so this module works unmodified after a future
      DATABASE_URL change.
"""

from __future__ import annotations

from collections.abc import Generator

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings

# --- Engine ---
#
# The Engine manages the actual connection pool to the database.
# It is created once, at import time, and reused for the lifetime of
# the application process.

# SQLite-specific connect argument. Only applied when the configured
# DATABASE_URL points at SQLite — harmless to omit for other databases,
# but explicitly gated here so PostgreSQL migrations don't need to touch
# this file.
# SQLite-specific connect argument. Only applied when the configured
# DATABASE_URL points at SQLite — harmless to omit for other databases,
# but explicitly gated here so PostgreSQL migrations don't need to touch
# this file.
connect_args: dict[str, bool] = {}
if settings.DATABASE_URL.lower().startswith("sqlite"):
    connect_args = {"check_same_thread": False}

engine: Engine = create_engine(
    settings.DATABASE_URL,
    connect_args=connect_args,
    # echo=True is useful for debugging SQL statements during development.
    # Tied to the DEBUG flag so production runs stay quiet by default.
    echo=settings.DEBUG,
    # Explicitly opt into SQLAlchemy 2.0-style engine behavior.
    future=True,
)

# --- Session Factory ---
#
# SessionLocal is a factory that produces new Session objects. Each
# Session represents a single "unit of work" — typically the lifetime
# of one incoming HTTP request.
#
#   autocommit=False:      we control commits explicitly in service code.
#   autoflush=False:       avoids surprising partial flushes before a
#                           query; we flush/commit explicitly when ready.
#   expire_on_commit=False: keeps attributes on committed objects readable
#                           after commit(), without triggering a fresh
#                           SELECT. This avoids DetachedInstanceError when
#                           a Pydantic schema serializes an ORM object
#                           after the session has already committed —
#                           a common pattern in FastAPI request handlers.
SessionLocal: sessionmaker[Session] = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
    expire_on_commit=False,
)


def get_db() -> Generator[Session, None, None]:
    """
    FastAPI dependency that yields a database session for a single request.

    Usage in a router:

        from fastapi import Depends
        from app.database.session import get_db

        @router.get("/students")
        def list_students(db: Session = Depends(get_db)):
            ...

    The session is always closed after the request completes, whether it
    succeeded or raised an exception — this prevents connection leaks.
    """
    db: Session = SessionLocal()
    try:
        yield db
    finally:
        db.close()
