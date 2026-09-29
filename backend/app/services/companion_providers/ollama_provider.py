"""
services/companion_providers/ollama_provider.py

Ollama-backed provider for Mira (Phase 14). Uses
app.llm.ollama_client (Module 1, Phase 11) EXCLUSIVELY for the HTTP
call — this file owns only the companion-specific prompt construction
and response validation, never HTTP/network logic directly.

Model-agnostic: never references a model name directly — that lives
solely in settings.OLLAMA_MODEL.
"""

from __future__ import annotations

from app.llm.ollama_client import OllamaGenerationError, generate
from app.services.companion_providers.base import (
    CompanionContext,
    CompanionGenerationResult,
    CompanionProvider,
)


class CompanionGenerationError(Exception):
    """
    Raised when Ollama-based companion message generation fails for
    any reason. Callers (FallbackCompanionProvider) catch this single
    exception type to trigger the template fallback.
    """


def _build_prompt(context: CompanionContext) -> str:
    """Build a prompt for a short, warm, in-character message from Mira."""
    details = [f"student name: {context.student_name}"]
    if context.recent_quiz_score is not None:
        details.append(f"recent quiz score: {context.recent_quiz_score:.0f}%")
    if context.recent_engagement_label is not None:
        details.append(f"recent engagement level: {context.recent_engagement_label}")
    if context.current_difficulty_level is not None:
        details.append(f"current difficulty level: {context.current_difficulty_level}")
    detail_text = "; ".join(details)

    student_message_part = ""
    if context.student_message:
        student_message_part = (
            f' The student just said: "{context.student_message}". '
            f"Respond directly to what they said, in character."
        )

    return (
        "You are Mira, a warm, encouraging, patient learning companion "
        "for a student on a neuroadaptive learning platform. Write a "
        "short (2-3 sentence) supportive message directly to the "
        "student. Respond with ONLY the message text, no preamble, no "
        "formatting, no quotation marks."
        f"{student_message_part} "
        f"Context: {detail_text}."
    )


class OllamaCompanionProvider(CompanionProvider):
    """
    Generates Mira's message via the locally-running Ollama model
    configured in settings.OLLAMA_MODEL. Raises
    CompanionGenerationError on any failure.
    """

    def generate_message(self, context: CompanionContext) -> CompanionGenerationResult:
        prompt = _build_prompt(context)

        try:
            raw_text = generate(prompt)
        except OllamaGenerationError as exc:
            raise CompanionGenerationError(
                f"Ollama companion generation failed: {exc}"
            ) from exc

        cleaned = raw_text.strip()
        if not cleaned:
            raise CompanionGenerationError("Ollama companion response was empty.")

        return CompanionGenerationResult(message=cleaned, generated_by="ollama")
