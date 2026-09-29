"""
database/__init__.py

Public API for the `app.database` package.

This file defines the single, canonical entry point the rest of the
application should use for anything database-related:

    from app.database import engine, SessionLocal, get_db, init_db

Why re-export here instead of importing individual submodules everywhere?
    Without this file, callers would need to know exactly which submodule
    each object lives in (`app.database.session` for `engine` and
    `get_db`, `app.database.init_db` for `init_db`). Centralizing the
    public API in the package `__init__.py` means:
        - Callers only need to remember one import path: `app.database`.
        - The internal file layout (session.py vs. init_db.py) can be
          reorganized later without breaking every import across the
          codebase — only this file would need to change.
        - It's immediately clear, from this one file, what the database
          package's supported public surface is.

Why this file does NOT create a new Engine or SessionLocal:
    `engine` and `SessionLocal` are already fully constructed, singleton
    objects defined in `session.py` (frozen, Module 1). This file only
    imports and re-exports those existing objects — it never calls
    `create_engine()` or `sessionmaker()` itself. If it did, the
    application would end up with two independent engines/session
    factories, which would be a serious bug: code using one `SessionLocal`
    could commit data that code using a second, separate `SessionLocal`
    wouldn't consistently see, and SQLite's file-based locking behavior
    would become unpredictable across two separate connection pools.
    Importing this package must always yield the exact same `engine` and
    `SessionLocal` objects that `session.py` created.

Why database initialization is NOT triggered automatically on import:
    `init_db()` creates database tables — a deliberate, meaningful action
    with real side effects on disk. If simply importing `app.database`
    (which can happen indirectly, e.g. a test file importing `get_db` for
    a fixture, or a static analysis tool inspecting the package) silently
    triggered table creation, that would violate the basic expectation
    that imports are side-effect-free. Initialization must instead be
    invoked explicitly and intentionally — either from the FastAPI
    application's startup lifecycle (see `main.py`, Module 6) or manually
    from the command line via `python -m app.database.init_db`. This file
    only makes `init_db` available to be called; it does not call it.
"""

from __future__ import annotations

from app.database.init_db import init_db
from app.database.session import SessionLocal, engine, get_db

# Explicit public API. Anything not listed here is considered an
# internal implementation detail of the `app.database` package and
# should not be imported directly from outside it.
__all__ = [
    "engine",
    "SessionLocal",
    "get_db",
    "init_db",
]
