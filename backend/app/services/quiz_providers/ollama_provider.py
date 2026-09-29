"""
services/quiz_providers/ollama_provider.py

Ollama-backed quiz generation provider (Master Specification Section
7). Uses app.llm.ollama_client (Module 1) exclusively for the HTTP
call — this file owns the quiz-specific prompt construction and
response parsing/validation, which the generic client deliberately
does not know about.

Returns the same QuizGenerationResult shape as FallbackQuizProvider
expects (source="ai_generated"), so quiz_service.py's usage of
QuizProvider is completely unaffected by which concrete provider is
active.

Model-agnostic: never references a model name directly — that lives
solely in settings.OLLAMA_MODEL, read by ollama_client.generate().
"""

from __future__ import annotations

import json

from pydantic import ValidationError

from app.llm.ollama_client import OllamaGenerationError, generate
from app.services.quiz_providers.base import (
    QuizGenerationResult,
    QuizProvider,
    QuizQuestionInternal,
)

_NUM_QUESTIONS = 5


class QuizGenerationError(Exception):
    """
    Raised when Ollama-based quiz generation fails for any reason —
    the underlying Ollama call failed, the response wasn't valid JSON,
    or the JSON didn't match the required question structure. Callers
    (FallbackQuizProvider) catch this single exception type to trigger
    the template fallback.
    """


def _build_prompt(difficulty_level: str, content_body: str | None = None) -> str:
    """
    Build a strict-JSON-output prompt for the given difficulty level.

    When content_body is provided (the actual lesson text the student
    just read), the questions must be derived from it — this is the
    entire point of AI-generated quizzes existing alongside the
    deterministic template provider: an AI quiz should be MORE
    contextually relevant than the template's sentence-extraction
    approach, not less. Without this, the model has nothing to work
    from except the difficulty label, and reliably falls back to
    generic filler (arithmetic, geography trivia) with no connection
    to what the student actually studied — exactly the "off-topic
    2+2 questions" failure mode this fixes.

    The previous version of this prompt also included a worked JSON
    example using "What is 2+2?" as a formatting template. That was a
    mistake independent of the content-awareness gap: models —
    especially smaller ones — will often echo a concrete example
    back nearly verbatim rather than treating it as a pure syntax
    guide, which is exactly what was observed happening. The revised
    prompt describes the required JSON *shape* in words only, with no
    concrete example content to copy.
    """
    base = (
        f"Generate exactly {_NUM_QUESTIONS} multiple-choice quiz questions "
        f"at '{difficulty_level}' difficulty level for a student learning "
        f"platform."
    )

    if content_body:
        topic_instruction = (
            f" The questions MUST be based directly on the following "
            f"lesson content the student just read — do not write "
            f"generic or unrelated questions (no arithmetic, no trivia "
            f"unless the lesson itself is about that topic). Every "
            f"question should test understanding of ideas that "
            f"actually appear in this text:\n\n"
            f'"""\n{content_body}\n"""\n'
        )
    else:
        topic_instruction = ""

    format_instruction = (
        f" Respond with ONLY a JSON array, no other text, no markdown "
        f"formatting, no explanation, and no <think> reasoning block — "
        f"output the JSON array immediately as your entire response. "
        f'Each array element must be a JSON object with exactly these '
        f'fields: "question_id" (a short unique string identifier), '
        f'"prompt" (the question text, as a string), "options" (a JSON '
        f'array of exactly 5 short answer strings, only one of which is '
        f'correct), and '
        f'"correct_option_index" (an integer — the zero-based index '
        f"into the options array of the correct answer)."
    )

    return base + topic_instruction + format_instruction


def _strip_markdown_fences(text: str) -> str:
    """Strip ```json / ``` fences if the model wrapped its output in them."""
    stripped = text.strip()
    if stripped.startswith("```"):
        lines = stripped.split("\n")
        lines = lines[1:]  # drop opening fence (with optional language tag)
        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]
        stripped = "\n".join(lines).strip()
    return stripped


def _strip_thinking_blocks(text: str) -> str:
    """
    Remove <think>...</think> reasoning blocks that "thinking" model
    families (including the Qwen3 series used by default here) commonly
    emit before their actual answer, even when a prompt explicitly asks
    for JSON-only output. Left unstripped, a leading <think> block makes
    every single response fail json.loads() — this was silently causing
    100% of Ollama quiz/reflection generations to fall back to the
    template provider on any model that reasons out loud by default.
    """
    import re
    return re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()


def _extract_json_array(text: str) -> str:
    """
    Extract the JSON array substring from a response that may include
    conversational prose before/after it (e.g. "Sure! Here are the
    questions: [...]. Let me know if you need more!") — another common
    small-model behaviour despite an explicit "respond with ONLY JSON"
    instruction. Finds the first '[' and its matching ']' by bracket
    depth, so nested arrays/objects inside the questions themselves
    (e.g. the "options" field) don't confuse the boundary.

    Returns the original text unchanged if no bracket pair is found,
    so the caller's json.loads() still raises a clear error rather than
    this function masking a genuinely empty/non-JSON response.
    """
    start = text.find("[")
    if start == -1:
        return text

    depth = 0
    for i in range(start, len(text)):
        if text[i] == "[":
            depth += 1
        elif text[i] == "]":
            depth -= 1
            if depth == 0:
                return text[start:i + 1]
    return text  # unbalanced — let json.loads() raise the real error


def _parse_questions(raw_text: str) -> list[QuizQuestionInternal]:
    """
    Parse and validate the model's raw text output into a list of
    QuizQuestionInternal. Raises QuizGenerationError on any structural
    problem.

    Cleaning happens in three stages, each handling a distinct and
    common small/"thinking"-model failure mode, applied in this order:
      1. Strip <think>...</think> reasoning blocks (Qwen3 default
         behaviour — the single most likely cause of 100% fallback
         rates when using a reasoning-capable model like qwen3:1.7b).
      2. Strip ```json markdown code fences.
      3. Extract the JSON array substring even if the model added
         conversational text before/after it.
    """
    cleaned = _strip_thinking_blocks(raw_text)
    cleaned = _strip_markdown_fences(cleaned)
    cleaned = _extract_json_array(cleaned)

    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise QuizGenerationError(f"Ollama quiz response was not valid JSON: {exc}") from exc

    if not isinstance(data, list) or not data:
        raise QuizGenerationError("Ollama quiz response was not a non-empty JSON array.")

    try:
        questions = [QuizQuestionInternal.model_validate(item) for item in data]
    except ValidationError as exc:
        raise QuizGenerationError(
            f"Ollama quiz response did not match the required question structure: {exc}"
        ) from exc

    # Defensive structural check beyond per-field validation: every
    # correct_option_index must actually be a valid index into that
    # question's own options list.
    for q in questions:
        if q.correct_option_index >= len(q.options):
            raise QuizGenerationError(
                f"Question '{q.question_id}' has correct_option_index "
                f"{q.correct_option_index} out of range for its options."
            )

    # Accept a slightly short response (smaller/weaker models sometimes
    # under-deliver on count) rather than failing outright, but reject
    # anything too thin to function as a real quiz. Falls back to the
    # template provider, which always returns exactly _NUM_QUESTIONS.
    _MIN_ACCEPTABLE_QUESTIONS = 3
    if len(questions) < _MIN_ACCEPTABLE_QUESTIONS:
        raise QuizGenerationError(
            f"Ollama returned only {len(questions)} question(s), "
            f"fewer than the minimum of {_MIN_ACCEPTABLE_QUESTIONS} needed "
            f"for a usable quiz."
        )

    return questions


class OllamaQuizProvider(QuizProvider):
    """
    Generates quiz questions via the locally-running Ollama model
    configured in settings.OLLAMA_MODEL. Raises QuizGenerationError on
    any failure — callers should catch this and fall back to
    TemplateQuizProvider (see FallbackQuizProvider).
    """

    def generate_quiz(
        self,
        difficulty_level: str,
        content_body: str | None = None,
    ) -> QuizGenerationResult:
        # content_body (the actual lesson text) is now threaded into the
        # prompt below — see _build_prompt's docstring for why this
        # previously being unused caused generic, off-topic questions
        # (e.g. arithmetic) regardless of what the lesson was about.
        prompt = _build_prompt(difficulty_level, content_body)

        try:
            raw_text = generate(prompt)
        except OllamaGenerationError as exc:
            raise QuizGenerationError(f"Ollama quiz generation failed: {exc}") from exc

        questions = _parse_questions(raw_text)
        return QuizGenerationResult(questions=questions, source="ai_generated")
