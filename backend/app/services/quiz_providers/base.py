"""
services/quiz_providers/base.py

Abstract quiz generation provider interface (Master Specification
Section 7, LLM Reliability).

The specification describes two quiz-generation mechanisms with the
same output contract: Ollama (generative AI) as the primary path, and
predefined template-based questions as the automatic fallback when
Ollama is unavailable. This interface is what makes that swap possible
without touching the service layer, routers, or database design later:

    QuizProvider (this file, abstract)
        -> TemplateQuizProvider (Phase 8)
        -> OllamaQuizProvider (Phase 11)
        -> FallbackQuizProvider (Phase 11, composes the two above)

All providers return the same QuizGenerationResult shape, so
quiz_service.py only ever depends on this interface, never on a
concrete provider.

Corrective note (Phase 11): generate_quiz() originally returned a bare
list[QuizQuestionInternal], with no indication of which provider
actually produced the questions. Once a real Ollama provider existed,
this made it impossible for quiz_service.py to persist an accurate
QuizAttempt.quiz_source — it was hardcoded to "template_fallback"
regardless of the true source. QuizGenerationResult fixes this by
carrying the source alongside the questions, returned by value (never
via shared/mutable provider state), so it is safe under concurrent
requests.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Literal

from pydantic import BaseModel, Field


class QuizQuestionInternal(BaseModel):
    """
    Full internal representation of a single quiz question, INCLUDING
    the correct answer. This is the server-side-only shape persisted
    into QuizAttempt.questions_json. It must never be returned directly
    to a client — see schemas.quiz_attempt.QuizQuestionOut for the
    answer-free public shape derived from this at read time.
    """

    question_id: str
    prompt: str
    options: list[str] = Field(..., min_length=2)
    correct_option_index: int = Field(..., ge=0)


class QuizGenerationResult(BaseModel):
    """
    Return value of generate_quiz(): the generated questions together
    with which provider actually produced them. `source` maps directly
    to the frozen QuizAttempt.quiz_source column's two valid values.
    """

    questions: list[QuizQuestionInternal]
    source: Literal["ai_generated", "template_fallback"]


class QuizProvider(ABC):
    """
    Abstract interface for quiz generation. Any concrete provider
    (template-based, Ollama-based, or a fallback composite of both)
    must implement this method and return the same structure, so
    quiz_service.py can call whichever provider is currently active
    without any code change elsewhere.
    """

    @abstractmethod
    def generate_quiz(
        self,
        difficulty_level: str,
        content_body: str | None = None,
    ) -> QuizGenerationResult:
        """
        Produce a full set of quiz questions (with correct answers) for
        the given difficulty level, tagged with which provider produced
        them. Called exactly once, at QuizAttempt creation time — never
        during grading/submission.

        content_body is the learning content the student just read.
        Providers that support content-aware generation (TemplateQuizProvider)
        use it to generate contextually relevant questions. Providers that
        don't (OllamaQuizProvider, which builds its own prompt) may ignore it.
        """
        raise NotImplementedError

