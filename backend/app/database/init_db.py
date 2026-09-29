"""
database/init_db.py

Database initialization.

This module's single responsibility is to create all database tables
from the ORM model metadata defined in `app/models/`. It does not define
or modify any model, engine, or configuration — it only consumes them.

Why `Base` is imported LAZILY, inside `init_db()`, instead of at module
level:
    `app/models/__init__.py` (frozen) imports every one of the 9 domain
    models in dependency order so SQLAlchemy's mapper registry sees all
    of them before any `relationship()` string reference is resolved.
    That file's very first statement is `from app.database.base import
    Base`. Meanwhile, `app/database/__init__.py` (frozen) imports this
    module (`init_db.py`). If THIS module also imported `app.models` at
    MODULE LEVEL (i.e. at the top of the file, executed the instant this
    module is first loaded), the two packages would form a real import
    cycle that only resolves successfully if `app.database` happens to
    already be mid-import before `app.models` starts loading — an
    order-dependent fragility that breaks for callers who import
    `app.models` first (e.g. `import app.models`, `from app.models
    import Student`, or any Alembic/test script that does the same).

    Moving `from app.models import Base` INSIDE the `init_db()` function
    body defers that import until the function is actually CALLED,
    rather than the moment this module is merely imported. By the time
    any caller actually invokes `init_db()`, both `app.database` and
    `app.models` are always fully loaded and registered in `sys.modules`
    (having already had every opportunity to resolve each other's
    submodule references), regardless of which package the caller
    imported first. This completely removes the import-time cycle
    without changing what `init_db()` does or which tables it creates.

Idempotency:
    `Base.metadata.create_all(engine)` only creates tables that do not
    already exist (SQLAlchemy checks this automatically, equivalent to
    `checkfirst=True`, which is the default). Running this script or
    calling `init_db()` multiple times is therefore always safe — it
    will never raise an error or duplicate existing tables.
"""

from __future__ import annotations

from app.database.session import engine


def init_db() -> None:
    """
    Create all database tables defined by the ORM models, if they do not
    already exist.

    This is safe to call multiple times (e.g. on every application
    startup) — SQLAlchemy will skip any table that already exists rather
    than raising an error or altering it.
    """
    # Imported here, INSIDE the function, rather than at module level.
    # See the module docstring above for why this specific placement is
    # what eliminates the order-dependent circular import between
    # `app.models` and `app.database`. By the time this function is
    # called, both packages are guaranteed to be fully loaded no matter
    # which one the caller imported first.
    from app.models import Base

    # Table names known to SQLAlchemy's metadata registry (i.e. tables
    # defined by the ORM models). This is NOT a query against the actual
    # database — it does not confirm what tables currently exist on disk.
    registered_tables = set(Base.metadata.tables.keys())

    print("Initializing Memora database...")
    print(f"   Target: {engine.url}")
    print(f"   Tables registered in ORM metadata: {len(registered_tables)}")

    Base.metadata.create_all(bind=engine)

    print("Database initialization complete.")
    print("   Tables registered in ORM metadata (now created if missing):")
    for table_name in sorted(registered_tables):
        print(f"     - {table_name}")


if __name__ == "__main__":
    # Allows running this file directly from the command line, e.g.:
    #     python -m app.database.init_db
    # Useful for first-time project setup or manual debugging, without
    # needing to start the full FastAPI application.
    init_db()
