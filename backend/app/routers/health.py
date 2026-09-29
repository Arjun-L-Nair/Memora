"""
Health check endpoint.

Used to verify that the API is running and reachable. Future tickets may
extend this to check database connectivity, but for the foundation ticket
it simply confirms the service is up.
"""

from fastapi import APIRouter

from app.core.config import get_settings

router = APIRouter(tags=["Health"])


@router.get("/health")
def health_check() -> dict:
    """Return basic service status information."""
    settings = get_settings()
    return {
        "status": "ok",
        "app_name": settings.app_name,
        "environment": settings.environment,
    }
