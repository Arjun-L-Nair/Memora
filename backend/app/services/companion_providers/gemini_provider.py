"""
services/companion_providers/gemini_provider.py

Google Gemini-backed provider for Mira (Memora overhaul, Component 2).
Replaces Ollama as the primary companion provider — see
implementation_plan.md's "API Choice" note and app/core/config.py's
GEMINI_* settings.

Uses google-generativeai directly (no separate llm/gemini_client.py
wrapper module, unlike the Ollama path, since the official SDK already
provides a clean, testable interface and this project has only one
Gemini-backed provider today; if a second one appears later, the
shared HTTP/retry logic should be extracted the same way
llm/ollama_client.py was).

System prompt encodes autism-specialist interaction patterns from the
plan: clear/concrete language (no idioms/sarcasm/ambiguity),
predictable structure, emotional validation before correction, social
story format on request, and visual/emoji anchors used purposefully
rather than decoratively.
"""

from __future__ import annotations

from app.core.config import settings
from app.services.companion_providers.base import (
    CompanionContext,
    CompanionGenerationResult,
    CompanionProvider,
)

_SYSTEM_PROMPT = """You are Mira, a warm, patient learning companion for an autistic \
student on an adaptive learning platform. Follow these interaction rules strictly:

1. Use clear, concrete, literal language. Avoid idioms, sarcasm, and ambiguous phrasing.
2. Keep a predictable structure: acknowledge how the student seems to be feeling first, \
   THEN respond to what they said or asked.
3. Validate the student's emotional state before offering correction or new information.
4. Keep responses short (2-4 sentences) unless asked for a social story or a longer \
   explanation.
5. If asked for a "social story", use a Carol Gray-style social story format: short, \
   literal sentences describing a situation, the student's likely feelings, and a \
   concrete suggested response — no metaphor.
6. If asked to explain a concept differently, break it into smaller, more concrete steps \
   rather than restating it more verbosely.
7. Use at most 1-2 emojis per message, only as a visual anchor for an emotion or concept \
   (e.g. a checkmark for "done"), never as decoration.
8. Never use sarcasm, rhetorical questions, or exaggeration ("literally dying", etc).
"""


class CompanionGenerationError(Exception):
    """Raised when Gemini-based companion message generation fails for any reason."""


def _build_prompt(context: CompanionContext) -> str:
    """Build the user-turn prompt (system instructions are sent separately)."""
    details = [f"student name: {context.student_name}"]
    if context.recent_quiz_score is not None:
        details.append(f"recent quiz score: {context.recent_quiz_score:.0f}%")
    if context.recent_engagement_label is not None:
        details.append(f"recent engagement level: {context.recent_engagement_label}")
    if context.current_difficulty_level is not None:
        details.append(f"current difficulty level: {context.current_difficulty_level}")
    if context.detected_emotion is not None:
        details.append(f"detected emotional state: {context.detected_emotion}")
    if context.sensory_sensitivity_score is not None:
        details.append(f"sensory sensitivity score (0-1, higher = more sensitive): {context.sensory_sensitivity_score:.2f}")
    detail_text = "; ".join(details)

    mode_instruction = ""
    if context.interaction_mode == "social_story":
        mode_instruction = " Write this as a Carol Gray-style social story."
    elif context.interaction_mode == "visual_schedule":
        mode_instruction = " Describe this as a simple, ordered step-by-step visual schedule."
    elif context.interaction_mode == "calm_down":
        mode_instruction = (
            " The student may be overwhelmed. Prioritize a short calming message and "
            "gently suggest a breathing exercise if it fits."
        )

    student_message_part = ""
    if context.student_message:
        student_message_part = f' The student just said: "{context.student_message}".'

    return (
        f"Context: {detail_text}.{student_message_part}"
        f"{mode_instruction} Respond with ONLY the message text, no preamble, "
        f"no quotation marks."
    )


class GeminiCompanionProvider(CompanionProvider):
    """
    Generates Mira's message via the Gemini API (settings.GEMINI_MODEL).
    Raises CompanionGenerationError on any failure (missing API key,
    network error, empty response, timeout) so the fallback chain can
    take over.
    """

    def generate_message(self, context: CompanionContext) -> CompanionGenerationResult:
        if not settings.GEMINI_API_KEY:
            raise CompanionGenerationError("GEMINI_API_KEY is not configured.")

        try:
            import google.generativeai as genai
        except ImportError as exc:  # pragma: no cover
            raise CompanionGenerationError(
                "google-generativeai package is not installed."
            ) from exc

        try:
            genai.configure(api_key=settings.GEMINI_API_KEY)
            model = genai.GenerativeModel(
                model_name=settings.GEMINI_MODEL,
                system_instruction=_SYSTEM_PROMPT,
            )

            # Build multi-turn history from the sliding window, mapping
            # this app's "student"/"mira" roles to Gemini's "user"/"model".
            history = [
                {
                    "role": "user" if turn["role"] == "student" else "model",
                    "parts": [turn["message"]],
                }
                for turn in context.conversation_history
            ]

            chat = model.start_chat(history=history)
            response = chat.send_message(
                _build_prompt(context),
                request_options={"timeout": settings.GEMINI_TIMEOUT_SECONDS},
            )
        except Exception as exc:
            raise CompanionGenerationError(f"Gemini companion generation failed: {exc}") from exc

        cleaned = (response.text or "").strip()
        if not cleaned:
            raise CompanionGenerationError("Gemini companion response was empty.")

        return CompanionGenerationResult(message=cleaned, generated_by="gemini")
