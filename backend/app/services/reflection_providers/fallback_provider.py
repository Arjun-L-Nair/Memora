"""
services/reflection_providers/fallback_provider.py

Composite reflection provider implementing the fallback chain (Memora
overhaul, Component 2):

    Gemini (primary)
      v (on any failure/timeout, or if GEMINI_API_KEY is unset)
    Ollama (only tried if settings.OLLAMA_ENABLED is True)
      v (on any failure/timeout, or if disabled)
    TemplateReflectionProvider (always succeeds)

Mirrors app.services.quiz_providers.fallback_provider.FallbackQuizProvider
exactly.
"""

from __future__ import annotations

import logging

from app.core.config import settings
from app.services.reflection_providers.base import (
    ReflectionContext,
    ReflectionGenerationResult,
    ReflectionProvider,
)
from app.services.reflection_providers.gemini_provider import (
    GeminiReflectionProvider,
    ReflectionGenerationError as GeminiReflectionGenerationError,
)
from app.services.reflection_providers.ollama_provider import (
    OllamaReflectionProvider,
    ReflectionGenerationError as OllamaReflectionGenerationError,
)
from app.services.reflection_providers.template_provider import TemplateReflectionProvider

logger = logging.getLogger(__name__)


class FallbackReflectionProvider(ReflectionProvider):
    """
    Tries Gemini first, then Ollama (only if enabled), then the
    deterministic template provider.
    """

    def __init__(
        self,
        primary: ReflectionProvider | None = None,
        secondary: ReflectionProvider | None = None,
        fallback: ReflectionProvider | None = None,
    ) -> None:
        self._primary = primary if primary is not None else GeminiReflectionProvider()
        self._secondary = secondary if secondary is not None else OllamaReflectionProvider()
        self._fallback = fallback if fallback is not None else TemplateReflectionProvider()

    def generate_reflection(self, context: ReflectionContext) -> ReflectionGenerationResult:
        # Broad Exception catch is deliberate here too — see the
        # matching comment in quiz_providers/fallback_provider.py.
        try:
            return self._primary.generate_reflection(context)
        except Exception as exc:
            logger.warning("Gemini reflection generation failed, trying next provider. Reason: %s", exc)

        if settings.OLLAMA_ENABLED:
            try:
                return self._secondary.generate_reflection(context)
            except Exception as exc:
                logger.warning("Ollama reflection generation failed, falling back to template. Reason: %s", exc)

        return self._fallback.generate_reflection(context)
