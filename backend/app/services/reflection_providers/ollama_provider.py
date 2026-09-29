"""
services/reflection_providers/ollama_provider.py

Ollama-backed Learning Reflection generation provider (Master
Specification Section 7). Uses app.llm.ollama_client (Module 1)
exclusively for the HTTP call — this file owns the reflection-specific
prompt construction and response validation.

Unlike quiz generation, a reflection is plain text (no JSON structure
required) — validation here is limited to confirming a non-empty
response was produced.

Model-agnostic: never references a model name directly.
"""

from __future__ import annotations

import re

from app.llm.ollama_client import OllamaGenerationError, generate
from app.services.reflection_providers.base import (
    ReflectionContext,
    ReflectionGenerationResult,
    ReflectionProvider,
)


class ReflectionGenerationError(Exception):
    """
    Raised when Ollama-based reflection generation fails for any
    reason. Callers (FallbackReflectionProvider) catch this single
    exception type to trigger the template fallback.
    """


def _strip_thinking_blocks(text: str) -> str:
    """
    Remove <think>...</think> reasoning blocks that "thinking" model
    families (including the Qwen3 series used by default here) commonly
    emit before their actual answer. Unlike quiz generation (which
    fails loudly on a <think> block because it breaks JSON parsing),
    a reflection is plain text — a leading <think> block here would
    NOT raise an error, it would silently be shown to the student as
    if it were their reflection message. This strip step exists
    specifically to prevent that.
    """
    return re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()


def _build_prompt(context: ReflectionContext) -> str:
    """Build a prompt for a short, encouraging, student-facing reflection."""
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
        "just completed. Respond with ONLY the reflection text, no "
        "preamble, no formatting, no quotation marks, and no <think> "
        "reasoning block — output the reflection text immediately as "
        f"your entire response. Session details: {detail_text}."
    )


class OllamaReflectionProvider(ReflectionProvider):
    """
    Generates a reflection via the locally-running Ollama model
    configured in settings.OLLAMA_MODEL. Raises
    ReflectionGenerationError on any failure.
    """

    def generate_reflection(self, context: ReflectionContext) -> ReflectionGenerationResult:
        prompt = _build_prompt(context)

        try:
            raw_text = generate(prompt)
        except OllamaGenerationError as exc:
            raise ReflectionGenerationError(
                f"Ollama reflection generation failed: {exc}"
            ) from exc

        cleaned = _strip_thinking_blocks(raw_text)
        if not cleaned:
            raise ReflectionGenerationError(
                "Ollama reflection response was empty after removing any "
                "<think> reasoning block."
            )

        return ReflectionGenerationResult(content=cleaned, generated_by="ollama")
