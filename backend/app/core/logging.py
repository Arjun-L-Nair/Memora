"""
Logging configuration for the application.

Provides a single `configure_logging` function that sets up a consistent,
readable log format across the whole backend. Other modules should obtain
loggers via `logging.getLogger(__name__)` after this has been called once
at startup (done in main.py).
"""

import logging
import sys

from app.core.config import get_settings


def configure_logging() -> None:
    """Configure the root logger for the application."""
    settings = get_settings()

    log_level = getattr(logging, settings.log_level.upper(), logging.INFO)

    logging.basicConfig(
        level=log_level,
        format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=[logging.StreamHandler(sys.stdout)],
    )

    # Keep noisy third-party loggers at a reasonable level.
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
