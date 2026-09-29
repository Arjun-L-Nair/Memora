"""
services/reflection_providers/gemini_provider.py

Gemini-backed Learning Reflection generation provider (Memora
overhaul, Component 2). Replaces Ollama as the primary
reflection-generation provider, mirroring
services/quiz_providers/gemini_provider.py's approach.

Reuses the prompt-building logic pattern from ollama_provider.py
(kept as a local _build_prompt here since reflection prompts are
simple enough not to warrant cross-module sharing, unlike quiz JSON
parsing).
"""

from __future__ import annotations

import re

from app.core.config import settings
from app.services.reflection_providers.base import (
    ReflectionContext,
    ReflectionGenerationResult,
    ReflectionProvider,
)


class ReflectionGenerationError(Exception):
    """Raised when Gemini-based reflection generation fails for any reason."""


def _strip_thinking_blocks(text: str) -> str:
    """Defensive strip in case a Gemini response ever includes a reasoning-style block."""
    return re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()


def _build_prompt(context: ReflectionContext) -> str:
    details = [f"difficulty level: {context.difficulty_level}"]
    if context.quiz_score is not None:
        details.append(f"quiz score: {context.quiz_score:.0f}%")
    if context.engagement_label is not None:
        details.append(f"engagement level: {context.engagement_label}")
    if context.time_spent_seconds is not None:
        details.append(f"time spent: {context.time_spent_seconds} seconds")

    detail_text = "; ".join(details)

    return (
        "Write a short (2-3 sentence), warm, encouraging reflection "
        "message directly to a student about the learning session they "
        "just completed. Use clear, concrete, literal language suitable "
        "for an autistic learner — avoid idioms, sarcasm, or ambiguous "
        "phrasing. Respond with ONLY the reflection text, no preamble, "
        f"no formatting, no quotation marks. Session details: {detail_text}."
    )


class GeminiReflectionProvider(ReflectionProvider):
    """
    Generates a reflection via the Gemini API (settings.GEMINI_MODEL).
    Raises ReflectionGenerationError on any failure.
    """

    def generate_reflection(self, context: ReflectionContext) -> ReflectionGenerationResult:
        if not settings.GEMINI_API_KEY:
            raise ReflectionGenerationError("GEMINI_API_KEY is not configured.")

        try:
            import google.generativeai as genai
        except ImportError as exc:  # pragma: no cover
            raise ReflectionGenerationError("google-generativeai package is not installed.") from exc

        prompt = _build_prompt(context)

        try:
            genai.configure(api_key=settings.GEMINI_API_KEY)
            model = genai.GenerativeModel(model_name=settings.GEMINI_MODEL)
            response = model.generate_content(
                prompt,
                request_options={"timeout": settings.GEMINI_TIMEOUT_SECONDS},
            )
            raw_text = response.text or ""
        except Exception as exc:
            raise ReflectionGenerationError(f"Gemini reflection generation failed: {exc}") from exc

        cleaned = _strip_thinking_blocks(raw_text)
        if not cleaned:
            raise ReflectionGenerationError("Gemini reflection response was empty.")

        return ReflectionGenerationResult(content=cleaned, generated_by="gemini")
