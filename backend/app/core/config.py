"""
core/config.py

Centralized application configuration.

This module defines the single source of truth for all environment-driven
configuration values (database connection, JWT auth settings, Ollama LLM
settings, and general environment/debug flags). It uses `pydantic-settings`
to read values from a `.env` file (and/or real OS environment variables,
which take precedence), validate their types, and expose them as a typed,
importable `settings` singleton.

Why centralize configuration here?
    Every other part of the application (database/session.py, future
    auth services, future Ollama integration, etc.) imports `settings`
    from this single module instead of reading environment variables
    directly. This guarantees there is exactly one definition, one
    default, and one validation rule for each configuration value —
    no risk of two files disagreeing about what a setting means.

Why Pydantic Settings?
    - Values are validated and type-coerced at application startup,
      not at first use. A malformed .env fails fast with a clear error
      instead of causing a confusing runtime crash later.
    - IDEs and type checkers can autocomplete/verify `settings.<field>`
      usage, catching typos that raw os.environ lookups would not.

Future PostgreSQL migration:
    DATABASE_URL is treated as an opaque connection string here — no
    SQLite-specific logic lives in this file (that branching is handled
    in database/session.py). Switching databases later requires only
    changing the DATABASE_URL value in .env; no code changes needed
    anywhere in the application.
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Anchor to this file's actual location on disk (backend/app/core/config.py
# -> backend/.env), NOT to the current working directory. A plain
# relative path like ".env" or "./memora.db" is resolved against
# whatever directory the process happened to be launched from — if
# `uvicorn app.main:app` is run from one directory and `alembic upgrade
# head` from another (e.g. a project root vs. the backend/ folder, or
# different IDE run configurations), pydantic-settings and Alembic
# silently read/create two DIFFERENT .env files and two DIFFERENT
# SQLite database files, each looking completely normal in isolation.
# This is the most common real-world cause of "my data disappeared
# after I reran the project" in a dev SQLite setup — nothing was
# actually lost, the app was just pointed at a different file. Fixing
# the .env path here does not fully fix the DATABASE_URL default
# below (SQLite connection strings are relative-by-convention and
# resolved by SQLAlchemy itself), but it does guarantee configuration
# loading is consistent regardless of launch directory, and the
# default DATABASE_URL is likewise anchored below for the same reason.
_BACKEND_DIR = Path(__file__).resolve().parent.parent.parent


class Settings(BaseSettings):
    """
    Typed application configuration, populated from environment variables
    and/or a `.env` file.

    Values with no default (e.g. SECRET_KEY) are REQUIRED — the
    application will refuse to start if they are missing, which is
    intentional: silently falling back to an insecure default secret
    would be dangerous.
    """

    # --- Database ---

    # SQLAlchemy-compatible connection string.
    # Example (SQLite, development):
    #   sqlite:///./memora.db
    # Example (PostgreSQL, future production):
    #   postgresql+psycopg2://user:password@host:5432/memora
    #
    # The default below is an ABSOLUTE path (backend/memora.db,
    # anchored via _BACKEND_DIR above), not a CWD-relative one. This
    # guarantees `uvicorn app.main:app` and `alembic upgrade head`
    # always read/write the exact same physical file regardless of
    # which directory each command happens to be launched from. If you
    # override DATABASE_URL yourself in .env with a relative path,
    # you're opting back into the CWD-dependent behavior — always launch
    # both uvicorn and alembic from the same directory in that case.
    DATABASE_URL: str = Field(
        default=f"postgresql+psycopg2://memora:memora@localhost:5432/memora",
        description=(
            "SQLAlchemy database connection string. Defaults to PostgreSQL "
            "for cloud deployment (Render/Railway). Override via .env for "
            "local SQLite development: sqlite:///./memora.db"
        ),
    )

    @field_validator("DATABASE_URL")
    @classmethod
    def _database_url_must_not_be_blank(cls, value: str) -> str:
        """
        Reject an empty or whitespace-only DATABASE_URL.

        Without this check, a misconfigured `.env` (e.g. `DATABASE_URL=`)
        would silently pass validation as an empty string and only fail
        later, with a confusing error, when SQLAlchemy tries to create
        an engine from it. Failing fast here gives a clear, immediate
        configuration error instead.
        """
        if not value or not value.strip():
            raise ValueError("DATABASE_URL must not be empty or whitespace.")
        return value

    @field_validator("DATABASE_URL")
    @classmethod
    def _resolve_relative_sqlite_path(cls, value: str) -> str:
        """
        Rewrite a CWD-relative SQLite URL (the conventional
        "sqlite:///./memora.db" form, as shipped in .env.example)
        into an absolute path anchored to the backend/ directory.

        Without this, `uvicorn app.main:app` and `alembic upgrade head`
        each resolve "./memora.db" against whatever directory THEY
        were launched from — if that differs between the two commands
        (a very easy mistake: e.g. one run from the project root, one
        from backend/, or different IDE run configurations), they
        silently create/read two separate SQLite files. Each looks
        completely normal in isolation, so the only visible symptom is
        "my data disappeared after a rerun" — nothing was actually
        lost, the app was just pointed at a different file the whole
        time. This validator makes that class of bug impossible by
        always resolving to the same absolute path regardless of
        launch directory, while leaving absolute paths and non-SQLite
        URLs (e.g. a real postgresql:// connection string) untouched.
        """
        prefix = "sqlite:///./"
        if value.startswith(prefix):
            relative_filename = value[len(prefix):]
            absolute_path = _BACKEND_DIR / relative_filename
            return f"sqlite:///{absolute_path}"
        return value

    # --- JWT Authentication ---
    # Used for Teacher (email/password) auth and short-lived Student
    # (PIN-based) session tokens, per Master Specification Section 6.

    # Secret key used to sign JWTs. REQUIRED — no insecure default.
    # Typed as SecretStr so the raw value is never accidentally exposed
    # in logs, tracebacks, or repr() output. Access the actual string
    # value only where strictly needed (e.g. JWT signing) via:
    #     settings.SECRET_KEY.get_secret_value()
    SECRET_KEY: SecretStr = Field(
        ...,
        description="Secret key used to sign JWT access/refresh tokens.",
        min_length=16,
    )

    # Signing algorithm. HS256 is the standard symmetric choice for a
    # single-backend academic project (no need for asymmetric RS256 here).
    JWT_ALGORITHM: str = Field(
        default="HS256",
        description="Algorithm used to sign JWT tokens.",
    )

    # How long a normal access token remains valid.
    ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(
        default=30,
        gt=0,
        description="Access token lifetime, in minutes.",
    )

    # How long a refresh token remains valid.
    REFRESH_TOKEN_EXPIRE_DAYS: int = Field(
        default=7,
        gt=0,
        description="Refresh token lifetime, in days.",
    )

    # --- Environment / Debug ---

    # Restricts to a known set of values so a typo (e.g. "prod" instead
    # of "production") is caught immediately at startup rather than
    # silently falling through conditional logic elsewhere.
    ENVIRONMENT: Literal["development", "testing", "production"] = Field(
        default="development",
        description="Current deployment environment.",
    )

    # Controls verbose behavior such as SQL echoing in database/session.py.
    # Should always be False in production.
    DEBUG: bool = Field(
        default=True,
        description="Enables verbose/debug behavior (e.g. SQL echo).",
    )

    # --- Ollama / Generative AI ---
    # Used for AI-generated quizzes and learning reflections, per Master
    # Specification Section 7. A 15-second timeout with fallback to
    # template-based content is required by the spec.

    # --- Google Gemini (Learning Companion "Mira", quizzes, reflections) ---
    # Replaces the local Ollama dependency. Free tier: 15 RPM, 1M tokens/day.
    GEMINI_API_KEY: str | None = Field(
        default=None,
        description="API key for Google Gemini. Required for Mira/quiz/reflection generation in production.",
    )

    GEMINI_MODEL: str = Field(
        default="gemini-2.0-flash",
        description="Gemini model used for companion chat, quiz, and reflection generation.",
    )

    GEMINI_TIMEOUT_SECONDS: int = Field(
        default=20,
        gt=0,
        description="Max time to wait for a Gemini response before falling back to template-based content.",
    )

    # --- Ollama (retained as optional legacy fallback, disabled by default) ---
    OLLAMA_ENABLED: bool = Field(
        default=False,
        description="If true, Ollama is tried before Gemini. Off by default now that Gemini is primary.",
    )

    OLLAMA_BASE_URL: str = Field(
        default="http://localhost:11434",
        description="Base URL of the local Ollama server (only used if OLLAMA_ENABLED=true).",
    )

    OLLAMA_MODEL: str = Field(
        default="qwen3:1.7b",
        description="Name of the local LLM model to use for generation.",
    )

    OLLAMA_TIMEOUT_SECONDS: int = Field(
        default=100,
        gt=0,
        description="Max time to wait for Ollama before falling back further (see GEMINI_TIMEOUT_SECONDS for the new primary path).",
    )

    # --- Development Admin Bootstrap ---
    # Optional. If both are set, and no Admin account exists yet, the
    # startup lifespan (app/main.py) creates exactly one Admin from
    # these values (see database/seed_dev_admin.py). This exists so a
    # fresh development database gets ONE admin automatically, without
    # requiring an admin-registration endpoint (per spec, Admin
    # accounts are provisioned, not self-registered). Leave unset in
    # any environment where automatic admin creation isn't wanted.
    DEV_ADMIN_EMAIL: str | None = Field(
        default=None,
        description="If set (with DEV_ADMIN_PASSWORD), bootstraps one dev Admin account on startup.",
    )

    DEV_ADMIN_PASSWORD: str | None = Field(
        default=None,
        description="Password for the bootstrapped dev Admin account. See DEV_ADMIN_EMAIL.",
    )

    # --- Pydantic Settings configuration ---
    model_config = SettingsConfigDict(
        # Load variables from backend/.env — an ABSOLUTE path (anchored
        # via _BACKEND_DIR above), not a bare ".env" resolved against
        # the current working directory. Without this anchor, running
        # `uvicorn app.main:app` from one directory and `alembic
        # upgrade head` from another silently loads two different .env
        # files (or one loads none at all and falls back to defaults),
        # which is the single most common cause of "my configuration
        # /data looks different after a rerun" in this kind of setup.
        # Real OS environment variables still take precedence over
        # values found in this file, which is useful for deployments
        # that inject configuration directly (e.g. containers, CI).
        env_file=str(_BACKEND_DIR / ".env"),
        env_file_encoding="utf-8",
        # Ignore unrelated environment variables instead of raising an
        # error, so the app doesn't break if the host environment has
        # unrelated variables set.
        extra="ignore",
        # Environment variable names are matched case-insensitively
        # (e.g. "database_url" and "DATABASE_URL" both work).
        case_sensitive=False,
        # Configuration should never change after startup. This makes
        # the settings object immutable, so accidental runtime mutation
        # (e.g. `settings.DEBUG = False` somewhere deep in the app) raises
        # an error instead of silently causing inconsistent behavior.
        frozen=True,
    )


# Singleton instance used throughout the application.
# Import this, not the Settings class, everywhere else:
#     from app.core.config import settings
settings = Settings()
