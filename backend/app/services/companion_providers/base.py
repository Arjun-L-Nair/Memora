"""
services/companion_providers/base.py

Abstract provider interface for Mira, the student learning companion
(Phase 14 — established by explicit project agreement; not defined in
the Master Specification).

Mirrors app.services.reflection_providers.base exactly, including the
source-tagged result pattern established as a corrective fix in Phase
11 — applied here from the start rather than retrofitted:

    CompanionProvider (this file, abstract)
        -> TemplateCompanionProvider (deterministic fallback)
        -> OllamaCompanionProvider (generative)
        -> FallbackCompanionProvider (composes the two above)

CompanionContext is a plain, ORM-independent input struct — this
module has no database dependency. The service layer is responsible
for populating it from real student/session/quiz/engagement data.

Named "companion" generically per project convention — "Mira" is the
product-facing name, used only in docstrings/response copy, never as
an identifier.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Literal

from pydantic import BaseModel


class CompanionContext(BaseModel):
    """
    Plain input to a companion provider — already-computed values only,
    no database objects.
    """

    student_name: str
    recent_engagement_label: str | None = None
    recent_quiz_score: float | None = None
    current_difficulty_level: str | None = None
    student_message: str | None = None

    # --- Memora overhaul additions ---
    # Sliding window of prior turns, oldest-first, each as
    # {"role": "student"|"mira", "message": str}. Populated by the
    # service layer from ConversationHistory (last 20 turns).
    conversation_history: list[dict[str, str]] = []
    # Detected emotion for the current student_message (see
    # ml/emotion_classifier.py), None if student_message is empty.
    detected_emotion: str | None = None
    # Sensory preferences, when set, so Mira can adapt tone/format
    # (e.g. shorter sentences for high sensory sensitivity).
    sensory_sensitivity_score: float | None = None
    # One of: "chat" (default), "social_story", "visual_schedule",
    # "calm_down" — selects an autism-specific interaction mode.
    interaction_mode: str = "chat"


class CompanionGenerationResult(BaseModel):
    """
    Return value of generate_message(): the companion's reply together
    with which provider actually produced it. `generated_by` follows
    the same convention as QuizGenerationResult.source and
    ReflectionGenerationResult.generated_by (Phase 11).
    """

    message: str
    generated_by: Literal["gemini", "ollama", "template"]


class CompanionProvider(ABC):
    """
    Abstract interface for Mira's message generation. Any concrete
    provider (template-based, Ollama-based, or a fallback composite of
    both) must implement this method and return the same structure.
    """

    @abstractmethod
    def generate_message(self, context: CompanionContext) -> CompanionGenerationResult:
        """
        Produce a short, supportive, student-facing message for the
        given context, tagged with which provider produced it.
        """
        raise NotImplementedError
