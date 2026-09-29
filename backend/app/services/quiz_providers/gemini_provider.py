"""
services/quiz_providers/gemini_provider.py

Gemini-backed quiz generation provider (Memora overhaul, Component 2).
Replaces Ollama as the primary quiz-generation provider — see
app/core/config.py's GEMINI_* settings and
services/companion_providers/gemini_provider.py for the equivalent
change already made to Mira's chat.

Reuses the prompt-building and response-parsing helpers from
ollama_provider.py (_build_prompt, _parse_questions) since that logic
is model-agnostic text processing (strip <think> blocks, strip
markdown fences, extract a JSON array, validate question structure) —
only the actual generation call differs between providers.
"""

from __future__ import annotations

from app.core.config import settings
from app.services.quiz_providers.base import QuizGenerationResult, QuizProvider
from app.services.quiz_providers.ollama_provider import _build_prompt, _parse_questions
from app.services.quiz_providers.ollama_provider import QuizGenerationError as OllamaQuizGenerationError


class QuizGenerationError(Exception):
    """
    Raised when Gemini-based quiz generation fails for any reason.
    Callers (FallbackQuizProvider) catch this single exception type to
    trigger the next provider in the chain.
    """


class GeminiQuizProvider(QuizProvider):
    """
    Generates quiz questions via the Gemini API (settings.GEMINI_MODEL).
    Raises QuizGenerationError on any failure (missing API key, network
    error, invalid JSON, structural validation failure).
    """

    def generate_quiz(
        self,
        difficulty_level: str,
        content_body: str | None = None,
    ) -> QuizGenerationResult:
        if not settings.GEMINI_API_KEY:
            raise QuizGenerationError("GEMINI_API_KEY is not configured.")

        try:
            import google.generativeai as genai
        except ImportError as exc:  # pragma: no cover
            raise QuizGenerationError("google-generativeai package is not installed.") from exc

        prompt = _build_prompt(difficulty_level, content_body)

        try:
            genai.configure(api_key=settings.GEMINI_API_KEY)
            model = genai.GenerativeModel(model_name=settings.GEMINI_MODEL)
            response = model.generate_content(
                prompt,
                request_options={"timeout": settings.GEMINI_TIMEOUT_SECONDS},
            )
            raw_text = response.text or ""
        except Exception as exc:
            raise QuizGenerationError(f"Gemini quiz generation failed: {exc}") from exc

        try:
            questions = _parse_questions(raw_text)
        except OllamaQuizGenerationError as exc:
            # _parse_questions raises the Ollama-named error type since
            # it's shared/reused code — re-raise as our own error type
            # so FallbackQuizProvider's except clause (which catches
            # THIS module's QuizGenerationError) works correctly.
            raise QuizGenerationError(str(exc)) from exc

        return QuizGenerationResult(questions=questions, source="ai_generated")
