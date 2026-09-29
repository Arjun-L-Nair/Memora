"""
services/reflection_providers/base.py

Abstract Learning Reflection generation provider interface (Master
Specification Section 6, 7).

Mirrors app.services.quiz_providers.base's three-tier pattern exactly:

    ReflectionProvider (this file, abstract)
        -> TemplateReflectionProvider (Module 3, deterministic fallback)
        -> OllamaReflectionProvider (Module 3, generative)
        -> FallbackReflectionProvider (Module 3, composes the two above)

All implementations return the same ReflectionGenerationResult shape,
so the future learning_reflection_service.py only ever depends on this
interface, never on a concrete provider.

ReflectionContext is a plain, ORM-independent input struct — this
module has no database dependency. The service layer is responsible
for populating it from real session/quiz/engagement data.

Corrective note (Module 5): generate_reflection() originally returned
a bare str, with no indication of which provider actually produced it
— identical to the QuizProvider defect corrected earlier in this
phase. ReflectionGenerationResult fixes this the same way: source
travels with the return value (never via shared/mutable provider
state), so learning_reflection_service.py can persist an accurate
LearningReflection.generated_by.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Literal

from pydantic import BaseModel


class ReflectionContext(BaseModel):
    """
    Plain input to a reflection provider — already-computed values
    only, no database objects.
    """

    difficulty_level: str
    quiz_score: float | None = None
    quiz_accuracy: float | None = None
    engagement_label: str | None = None
    time_spent_seconds: int | None = None


class ReflectionGenerationResult(BaseModel):
    """
    Return value of generate_reflection(): the reflection text together
    with which provider actually produced it. `generated_by` maps
    directly to the frozen LearningReflection.generated_by column's
    two valid values.
    """

    content: str
    generated_by: Literal["gemini", "ollama", "template"]


class ReflectionProvider(ABC):
    """
    Abstract interface for Learning Reflection generation. Any concrete
    provider (template-based, Ollama-based, or a fallback composite of
    both) must implement this method and return the same structure.
    """

    @abstractmethod
    def generate_reflection(self, context: ReflectionContext) -> ReflectionGenerationResult:
        """
        Produce a short, student-facing reflection paragraph for the
        given session context, tagged with which provider produced it.
        """
        raise NotImplementedError
