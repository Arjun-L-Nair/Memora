"""
main.py

FastAPI application entry point for Memora.

This file is intentionally minimal in scope. It is responsible ONLY for:
    - Creating and configuring the FastAPI application instance.
    - Running database initialization at startup.
    - Exposing basic health-check endpoints.
    - Providing a clear, documented place to register future routers.

It does NOT implement authentication, business logic, machine learning,
Ollama integration, or any domain API endpoints — those belong in their
own routers/services, registered here only once they exist.

--------------------------------------------------------------------------
Why `lifespan` instead of the deprecated `@app.on_event("startup")`?
--------------------------------------------------------------------------
FastAPI's `@app.on_event("startup")` / `@app.on_event("shutdown")`
decorators are deprecated. The modern replacement is a single `lifespan`
async context manager: code before the `yield` runs on startup, and code
after the `yield` runs on shutdown. This is preferred because it keeps
the startup/shutdown pairing structurally explicit in one place, rather
than relying on two separately-registered callbacks whose relationship
is only implicit.

--------------------------------------------------------------------------
Why is init_db() called here, specifically?
--------------------------------------------------------------------------
`app.database` (see database/__init__.py, Module 5) deliberately does
NOT call `init_db()` automatically on import — importing a package must
never have side effects like writing to disk. `main.py`, by contrast,
represents the moment the application is genuinely starting up to serve
real traffic. Calling `init_db()` inside `lifespan` makes database
readiness an explicit, logged, ordered part of that startup sequence,
guaranteed to run before the app begins accepting requests.

--------------------------------------------------------------------------
Why is create_all() (via init_db()) acceptable during development?
--------------------------------------------------------------------------
For an academic SQLite-backed project, `create_all()` is a lightweight,
zero-configuration way to guarantee the schema exists on first run —
nobody needs to remember a separate manual migration step just to get
the app running. It is non-destructive: it only creates tables that do
not yet exist, and never alters or drops existing tables or data.

--------------------------------------------------------------------------
How this evolves once Alembic migrations are introduced (see Module 7)
--------------------------------------------------------------------------
Once Alembic migrations exist, `create_all()` becomes redundant for
schema changes — those should instead flow through versioned migration
files applied via `alembic upgrade head`, typically as an explicit
deploy/CI step rather than an automatic part of application startup.
At that point, this file's call to `init_db()` would either be removed
entirely (with migrations run separately) or retained only as a
development-time convenience, gated behind
`settings.ENVIRONMENT == "development"`. No such change is made yet —
this is noted here so the intended evolution is clear when Alembic is
introduced.
"""

from __future__ import annotations

import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from slowapi.util import get_remote_address

from app.core.config import settings
from app.database import init_db
from app.database.migration_check import check_migrations_current
from app.database.seed_dev_admin import seed_dev_admin
from app.database.seed_skills import seed_skills_on_startup

# --- CORS configuration ---
#
# The frontend (Vite dev server, http://localhost:5173) and backend
# (http://localhost:8000) run on different origins during development,
# so the browser enforces CORS on every request. Without this, the
# frontend cannot call the API at all — every request is blocked
# client-side before it reaches FastAPI.
#
# Scoped to known local development origins only (Phase 16 integration
# fix, not a general-purpose "allow everything" policy). If a production
# frontend origin is introduced later, it should be added here explicitly
# rather than widened to a wildcard.
ALLOWED_ORIGINS = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]

# --- Logging ---
#
# A simple, standard-library logging configuration so startup/shutdown
# messages (and SQLAlchemy's own logger, when DEBUG/echo is enabled) are
# actually visible on the console. This is intentionally minimal — no
# custom logging framework or handler hierarchy is introduced here.
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("memora")

# --- OpenAPI tag metadata ---
#
# Placeholders for future routers. Declaring tags here now means the
# generated OpenAPI docs (/docs) will show a stable, organized grouping
# as each router is added later — no router is registered yet.
tags_metadata = [
    {"name": "Authentication", "description": "Teacher and student authentication."},
    {"name": "Students", "description": "Student account management."},
    {"name": "Teachers", "description": "Teacher account management."},
    {"name": "Learning Plans", "description": "Learning plan management."},
    {"name": "Learning Content", "description": "Instructional material within learning plans."},
    {"name": "Learning Sessions", "description": "Learning session tracking."},
    {"name": "Quiz", "description": "AI-generated and fallback quizzes."},
    {"name": "Analytics", "description": "Teacher analytics and reporting."},
    {"name": "AI", "description": "Engagement prediction and adaptive suggestions."},
    {"name": "Admin", "description": "Administrator oversight of teachers and students."},
]


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    Application lifespan handler.

    Code before `yield` runs once, at startup, before the app begins
    accepting requests. Code after `yield` runs once, at shutdown, after
    the app stops accepting new requests.
    """
    # --- Startup ---
    logger.info("Memora is starting up...")

    init_db()
    logger.info("Database initialization completed successfully.")

    # Read-only diagnostic: warns loudly (but never blocks startup) if
    # the connected database's Alembic revision is behind the latest
    # migration. init_db() above only CREATES missing tables — it is a
    # silent no-op for tables that already exist with an outdated
    # schema, so without this check a stale database can start the app
    # with zero errors and only fail later, confusingly, the first
    # time a feature touches a column added by a newer migration.
    check_migrations_current()

    # Populates the predefined skills library (3 Easy, 5 Medium, 7 Hard
    # skills) on a fresh database. Idempotent — a no-op once already
    # seeded. Runs in every environment, unlike seed_dev_admin below:
    # the skill library is real application content every deployment
    # needs, not development-only convenience data.
    seed_skills_on_startup()

    # Bootstraps exactly one Admin account on a fresh database, if
    # DEV_ADMIN_EMAIL/DEV_ADMIN_PASSWORD are configured. Restricted to
    # non-production environments as an extra safety margin, even
    # though seed_dev_admin() already refuses to run without both
    # settings configured and never overwrites an existing admin.
    if settings.ENVIRONMENT != "production":
        seed_dev_admin()

    logger.info("Memora startup complete. Ready to accept requests.")

    yield  # Application runs while suspended here.

    # --- Shutdown ---
    logger.info("Memora is shutting down gracefully.")


# --- FastAPI Application ---

app = FastAPI(
    title="Memora",
    description="AI-Driven Neuroadaptive Learning Framework",
    version="1.0.0",
    openapi_tags=tags_metadata,
    lifespan=lifespan,
)

# --- Rate limiting (production hardening, Memora overhaul) ---
#
# Per-IP rate limiting via slowapi, applied globally through
# SlowAPIMiddleware. Individual routers/routes may declare tighter
# limits later (e.g. login endpoints) via @limiter.limit("5/minute")
# decorators using this same `limiter` instance, imported from here.
limiter = Limiter(key_func=get_remote_address, default_limits=["120/minute"])
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(SlowAPIMiddleware)


# --- Router Registration ---
#
# Routers are added here once their modules exist. Only routers that
# actually exist are registered; remaining entries stay as placeholders
# until their own modules are implemented in a future phase.

from app.api.v1 import auth  # noqa: E402
from app.api.v1 import students  # noqa: E402
from app.api.v1 import learning_plans  # noqa: E402
from app.api.v1 import learning_content  # noqa: E402
from app.api.v1 import learning_sessions  # noqa: E402
from app.api.v1 import quiz  # noqa: E402
from app.api.v1 import student_learning  # noqa: E402
from app.api.v1 import ai  # noqa: E402
from app.api.v1 import learning_reflection  # noqa: E402
from app.api.v1 import analytics  # noqa: E402
from app.api.v1 import admin  # noqa: E402
from app.api.v1 import learning_companion  # noqa: E402
from app.api.v1 import early_warning  # noqa: E402
from app.api.v1 import sensory_profile  # noqa: E402
from app.api.v1 import skills  # noqa: E402

app.include_router(auth.router)
app.include_router(students.router)
app.include_router(learning_plans.router)
app.include_router(learning_content.router)
app.include_router(learning_sessions.router)
app.include_router(quiz.router)
app.include_router(student_learning.router)
app.include_router(ai.router)
app.include_router(learning_reflection.router)
app.include_router(analytics.router)
app.include_router(admin.router)
app.include_router(learning_companion.router)
app.include_router(early_warning.router)
app.include_router(sensory_profile.router)
app.include_router(skills.router)

# from app.api.v1 import teachers
# app.include_router(teachers.router)


# --- Response Models ---
#
# Simple Pydantic schemas describing the shape of the two health-check
# endpoints below. Using response_model gives FastAPI a typed contract
# to validate against and document in the OpenAPI schema, instead of
# relying only on the bare dict returned by each route function.


class RootResponse(BaseModel):
    """Response shape for the root (`/`) endpoint."""

    application: str
    status: str
    version: str


class HealthResponse(BaseModel):
    """Response shape for the `/health` endpoint."""

    status: str
    database_initialized: bool
    environment: str
    version: str


# --- Health Endpoints ---


@app.get("/", tags=["Health"], response_model=RootResponse)
def read_root() -> RootResponse:
    """
    Root endpoint. Confirms the application is running.

    Does not query the database or any dependent service.
    """
    return RootResponse(
        application="Memora",
        status="running",
        version="1.0.0",
    )


@app.get("/health", tags=["Health"], response_model=HealthResponse)
def health_check() -> HealthResponse:
    """
    Health check endpoint.

    Reports basic application status without querying the database.
    `database_initialized` reflects that `init_db()` ran successfully
    during startup (see `lifespan` above) — it is NOT a live database
    query, and does not confirm the database is currently reachable.
    """
    return HealthResponse(
        status="ok",
        database_initialized=True,
        environment=settings.ENVIRONMENT,
        version="1.0.0",
    )
