"""
services/companion_providers/fallback_provider.py

Composite provider implementing Mira's fallback chain (Memora
overhaul, Component 2):

    Gemini (primary)
      v (on any failure/timeout, or if GEMINI_API_KEY is unset)
    Ollama (only tried if settings.OLLAMA_ENABLED is True)
      v (on any failure/timeout, or if disabled)
    TemplateCompanionProvider (always succeeds)

No request ever fails solely because Gemini (or Ollama) is
unavailable - see app/core/config.py for OLLAMA_ENABLED/GEMINI_*.
"""

from __future__ import annotations

from app.core.config import settings
from app.services.companion_providers.base import (
    CompanionContext,
    CompanionGenerationResult,
    CompanionProvider,
)
from app.services.companion_providers.gemini_provider import (
    CompanionGenerationError as GeminiGenerationError,
    GeminiCompanionProvider,
)
from app.services.companion_providers.ollama_provider import (
    CompanionGenerationError as OllamaGenerationError,
    OllamaCompanionProvider,
)
from app.services.companion_providers.template_provider import TemplateCompanionProvider


class FallbackCompanionProvider(CompanionProvider):
    """
    Tries Gemini first, then Ollama (only if enabled), then the
    deterministic template provider.
    """

    def __init__(
        self,
        primary: CompanionProvider | None = None,
        secondary: CompanionProvider | None = None,
        fallback: CompanionProvider | None = None,
    ) -> None:
        self._primary = primary if primary is not None else GeminiCompanionProvider()
        self._secondary = secondary if secondary is not None else OllamaCompanionProvider()
        self._fallback = fallback if fallback is not None else TemplateCompanionProvider()

    def generate_message(self, context: CompanionContext) -> CompanionGenerationResult:
        # Broad Exception catch is deliberate: this chain's entire
        # purpose is "the app must never fail just because an AI
        # provider misbehaves." See the matching comment in
        # quiz_providers/fallback_provider.py.
        try:
            return self._primary.generate_message(context)
        except Exception:
            pass

        if settings.OLLAMA_ENABLED:
            try:
                return self._secondary.generate_message(context)
            except Exception:
                pass

        return self._fallback.generate_message(context)
