"""
services/quiz_providers/fallback_provider.py

Composite quiz provider implementing the fallback chain (Memora
overhaul, Component 2):

    Gemini (primary)
      v (on any failure/timeout, or if GEMINI_API_KEY is unset)
    Ollama (only tried if settings.OLLAMA_ENABLED is True)
      v (on any failure/timeout, or if disabled)
    TemplateQuizProvider (always succeeds)

This is the ONLY provider quiz_service.py needs to be aware of as its
_ACTIVE_PROVIDER. No request ever fails solely because Gemini (or
Ollama) is unavailable - see app/core/config.py for
OLLAMA_ENABLED/GEMINI_*.
"""

from __future__ import annotations

import logging

from app.core.config import settings
from app.services.quiz_providers.base import QuizGenerationResult, QuizProvider
from app.services.quiz_providers.gemini_provider import (
    GeminiQuizProvider,
    QuizGenerationError as GeminiQuizGenerationError,
)
from app.services.quiz_providers.ollama_provider import OllamaQuizProvider, QuizGenerationError as OllamaQuizGenerationError
from app.services.quiz_providers.template_provider import TemplateQuizProvider

logger = logging.getLogger(__name__)


class FallbackQuizProvider(QuizProvider):
    """
    Tries Gemini first, then Ollama (only if enabled), then the
    deterministic template provider.
    """

    def __init__(
        self,
        primary: QuizProvider | None = None,
        secondary: QuizProvider | None = None,
        fallback: QuizProvider | None = None,
    ) -> None:
        self._primary = primary if primary is not None else GeminiQuizProvider()
        self._secondary = secondary if secondary is not None else OllamaQuizProvider()
        self._fallback = fallback if fallback is not None else TemplateQuizProvider()

    def generate_quiz(
        self,
        difficulty_level: str,
        content_body: str | None = None,
    ) -> QuizGenerationResult:
        # Catches Exception broadly (not just GeminiQuizGenerationError)
        # deliberately: this chain's entire purpose is "the app must
        # never fail just because an AI provider misbehaves." A
        # provider raising something other than its own documented
        # error type (a bug in that provider, an unexpected SDK
        # exception, a test double, etc.) should still fall through to
        # the next tier rather than crash the request.
        try:
            return self._primary.generate_quiz(difficulty_level, content_body)
        except Exception as exc:
            logger.warning("Gemini quiz generation failed, trying next provider. Reason: %s", exc)

        if settings.OLLAMA_ENABLED:
            try:
                return self._secondary.generate_quiz(difficulty_level, content_body)
            except Exception as exc:
                logger.warning("Ollama quiz generation failed, falling back to template. Reason: %s", exc)

        return self._fallback.generate_quiz(difficulty_level, content_body)
