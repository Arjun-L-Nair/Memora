"""
tests/test_ollama_reliability.py

Covers Phase 16 Section 9 (Ollama / Generative AI Reliability) and
Section 10 (Learning Reflection)'s fallback requirement.

IMPORTANT SCOPE NOTE — read before interpreting these results:

These tests verify the CLIENT/PROVIDER CONTRACT using mocked HTTP
responses (via monkeypatching httpx.post), and the FALLBACK COMPOSITION
logic using dependency-injected fake providers (the codebase's own
primary/fallback constructor parameters, not a monkeypatch of frozen
internals). They do NOT start, mock, or simulate a running Ollama
server end-to-end, and they do NOT verify that a real Ollama server
plus the configured model (settings.OLLAMA_MODEL) actually produces
usable output.

Three distinct claims, kept separate here and in the ticket report:
    1. Real Ollama unavailable behavior — already observed live in
       Tickets D, G, and H2's own HTTP-level test below: every quiz/
       reflection generation call in this environment naturally hits
       the fallback path, because no Ollama server is reachable here.
    2. Mocked Ollama success/timeout/error scenarios — covered in this
       file, at the client and provider level, using mocked HTTP
       responses standing in for what a real server's response would
       look like in each case.
    3. Actual Ollama server/model availability and output quality —
       NOT verified by any test in this suite or this ticket. That
       would require a real, running Ollama instance with the
       configured model, which is outside this test environment.
"""

from __future__ import annotations

import httpx
import pytest

from app.llm.ollama_client import OllamaGenerationError, generate
from app.services.quiz_providers.base import (
    QuizGenerationResult,
    QuizProvider,
    QuizQuestionInternal,
)
from app.services.quiz_providers.fallback_provider import FallbackQuizProvider
from app.services.quiz_providers.ollama_provider import (
    OllamaQuizProvider,
    QuizGenerationError,
    _build_prompt,
)
from app.services.quiz_providers.template_provider import TemplateQuizProvider
from app.services.reflection_providers.base import (
    ReflectionContext,
    ReflectionGenerationResult,
    ReflectionProvider,
)
from app.services.reflection_providers.fallback_provider import FallbackReflectionProvider
from app.services.reflection_providers.ollama_provider import (
    OllamaReflectionProvider,
    ReflectionGenerationError,
)
from app.services.reflection_providers.template_provider import TemplateReflectionProvider
from tests.conftest import auth_header


# ==========================================================================
# 1. CLIENT LEVEL — app.llm.ollama_client.generate(), mocked httpx.post
#    ("Mocked Ollama scenario" — see module docstring, claim #2.)
# ==========================================================================


class _FakeResponse:
    def __init__(self, status_code: int, json_body=None, text: str = ""):
        self.status_code = status_code
        self._json_body = json_body
        self.text = text

    def json(self):
        if self._json_body is None:
            raise ValueError("no JSON body")
        return self._json_body


def test_client_raises_on_connection_error(monkeypatch):
    def _raise_connect_error(*args, **kwargs):
        raise httpx.ConnectError("Connection refused")

    monkeypatch.setattr(httpx, "post", _raise_connect_error)
    with pytest.raises(OllamaGenerationError):
        generate("test prompt")


def test_client_raises_on_timeout(monkeypatch):
    def _raise_timeout(*args, **kwargs):
        raise httpx.TimeoutException("timed out")

    monkeypatch.setattr(httpx, "post", _raise_timeout)
    with pytest.raises(OllamaGenerationError) as excinfo:
        generate("test prompt")
    assert "timed out" in str(excinfo.value).lower()


def test_client_raises_on_non_200_status(monkeypatch):
    monkeypatch.setattr(
        httpx, "post", lambda *a, **k: _FakeResponse(500, text="internal server error")
    )
    with pytest.raises(OllamaGenerationError):
        generate("test prompt")


def test_client_raises_on_malformed_json_body(monkeypatch):
    monkeypatch.setattr(httpx, "post", lambda *a, **k: _FakeResponse(200, json_body=None))
    with pytest.raises(OllamaGenerationError):
        generate("test prompt")


def test_client_raises_on_missing_response_field(monkeypatch):
    monkeypatch.setattr(
        httpx, "post", lambda *a, **k: _FakeResponse(200, json_body={"unexpected": "shape"})
    )
    with pytest.raises(OllamaGenerationError):
        generate("test prompt")


def test_client_raises_on_empty_response_field(monkeypatch):
    monkeypatch.setattr(httpx, "post", lambda *a, **k: _FakeResponse(200, json_body={"response": ""}))
    with pytest.raises(OllamaGenerationError):
        generate("test prompt")


def test_client_returns_text_on_valid_mocked_success(monkeypatch):
    """
    Mocked-success contract test only — see module docstring claim #2.
    This does NOT verify a real Ollama server or model; it verifies
    that generate() correctly extracts and returns the "response"
    field when the HTTP layer behaves as Ollama's real API documents.
    """
    monkeypatch.setattr(
        httpx, "post", lambda *a, **k: _FakeResponse(200, json_body={"response": "hello world"})
    )
    assert generate("test prompt") == "hello world"


# ==========================================================================
# 2. QUIZ PROVIDER LEVEL — OllamaQuizProvider, mocked app-level generate()
# ==========================================================================


def test_ollama_quiz_provider_parses_valid_json_array(monkeypatch):
    valid_json = (
        '[{"question_id": "q1", "prompt": "2+2?", "options": ["3", "4"], '
        '"correct_option_index": 1}, '
        '{"question_id": "q2", "prompt": "3+3?", "options": ["5", "6"], '
        '"correct_option_index": 1}, '
        '{"question_id": "q3", "prompt": "4+4?", "options": ["7", "8"], '
        '"correct_option_index": 1}]'
    )
    monkeypatch.setattr(
        "app.services.quiz_providers.ollama_provider.generate", lambda prompt: valid_json
    )
    result = OllamaQuizProvider().generate_quiz("Beginner")
    assert result.source == "ai_generated"
    assert len(result.questions) == 3
    assert result.questions[0].correct_option_index == 1


def test_ollama_quiz_provider_strips_markdown_fences(monkeypatch):
    fenced = (
        "```json\n"
        '[{"question_id": "q1", "prompt": "2+2?", "options": ["3", "4"], '
        '"correct_option_index": 1}, '
        '{"question_id": "q2", "prompt": "3+3?", "options": ["5", "6"], '
        '"correct_option_index": 1}, '
        '{"question_id": "q3", "prompt": "4+4?", "options": ["7", "8"], '
        '"correct_option_index": 1}]\n'
        "```"
    )
    monkeypatch.setattr(
        "app.services.quiz_providers.ollama_provider.generate", lambda prompt: fenced
    )
    result = OllamaQuizProvider().generate_quiz("Beginner")
    assert result.source == "ai_generated"
    assert len(result.questions) == 3


def test_ollama_quiz_provider_strips_thinking_block(monkeypatch):
    """
    Regression test: "thinking" model families (including the Qwen3
    series used by default — OLLAMA_MODEL=qwen3:1.7b) commonly emit a
    <think>...</think> reasoning block before their actual answer, even
    when explicitly instructed not to. Before this fix, any such
    response failed json.loads() immediately, meaning Ollama appeared
    to "always fail" and the template fallback fired on 100% of
    requests regardless of timeout settings.
    """
    response_with_thinking = (
        "<think>The user wants quiz questions, let me think about "
        "good options for this difficulty level...</think>\n"
        '[{"question_id": "q1", "prompt": "2+2?", "options": ["3", "4"], '
        '"correct_option_index": 1}, '
        '{"question_id": "q2", "prompt": "3+3?", "options": ["5", "6"], '
        '"correct_option_index": 1}, '
        '{"question_id": "q3", "prompt": "4+4?", "options": ["7", "8"], '
        '"correct_option_index": 1}]'
    )
    monkeypatch.setattr(
        "app.services.quiz_providers.ollama_provider.generate",
        lambda prompt: response_with_thinking,
    )
    result = OllamaQuizProvider().generate_quiz("Beginner")
    assert result.source == "ai_generated"
    assert len(result.questions) == 3


def test_ollama_quiz_provider_extracts_json_from_conversational_wrapper(monkeypatch):
    """
    Regression test: small models often wrap valid JSON in
    conversational prose ("Sure! Here are the questions: [...]. Let me
    know if you need more!") despite an explicit "respond with ONLY
    JSON" instruction. The parser must locate and extract the JSON
    array rather than failing on the surrounding text.
    """
    response_with_prose = (
        "Sure! Here are 3 quiz questions for you:\n\n"
        '[{"question_id": "q1", "prompt": "2+2?", "options": ["3", "4"], '
        '"correct_option_index": 1}, '
        '{"question_id": "q2", "prompt": "3+3?", "options": ["5", "6"], '
        '"correct_option_index": 1}, '
        '{"question_id": "q3", "prompt": "4+4?", "options": ["7", "8"], '
        '"correct_option_index": 1}]\n\n'
        "Let me know if you need anything else!"
    )
    monkeypatch.setattr(
        "app.services.quiz_providers.ollama_provider.generate",
        lambda prompt: response_with_prose,
    )
    result = OllamaQuizProvider().generate_quiz("Beginner")
    assert result.source == "ai_generated"
    assert len(result.questions) == 3


def test_build_prompt_includes_lesson_content_when_provided():
    """
    Regression test: the Ollama prompt previously only ever included
    difficulty_level, never the actual lesson content the student read
    — meaning the model had nothing topic-relevant to work from and
    reliably produced generic filler (arithmetic, trivia) regardless
    of what the lesson was actually about. The prompt must now embed
    the real content_body text whenever it's supplied.
    """
    body = "Emotions are feelings that happen inside us. Everyone has emotions every day."
    prompt = _build_prompt("Beginner", content_body=body)

    assert body in prompt
    assert "MUST be based directly on" in prompt


def test_build_prompt_does_not_reference_content_when_absent():
    """
    When no content_body is available (e.g. a session somehow has no
    linked content), the prompt must still be well-formed and must not
    reference lesson content that doesn't exist.
    """
    prompt = _build_prompt("Beginner", content_body=None)

    assert "MUST be based directly on" not in prompt
    assert "Generate exactly 5" in prompt


def test_build_prompt_no_longer_leaks_generic_example_question():
    """
    Regression test: the prompt previously included a concrete worked
    example -- 'What is 2+2?' -- as a JSON formatting template. Smaller
    models frequently echo a concrete example back nearly verbatim
    rather than treating it as pure syntax guidance, which is exactly
    what was observed in practice (quizzes about emotions/social
    skills lessons containing arithmetic questions). The prompt must
    describe the required JSON shape without any concrete example
    question content for the model to copy.
    """
    prompt = _build_prompt("Beginner", content_body="Some lesson about feelings.")
    assert "2+2" not in prompt
    assert "2 + 2" not in prompt


def test_ollama_quiz_provider_passes_content_body_through_to_prompt(monkeypatch):
    """
    End-to-end check that OllamaQuizProvider.generate_quiz() actually
    forwards content_body into the prompt sent to Ollama, rather than
    silently discarding it (the exact bug this fix addresses).
    """
    captured_prompts = []

    def fake_generate(prompt: str) -> str:
        captured_prompts.append(prompt)
        return (
            '[{"question_id": "q1", "prompt": "p1", "options": ["a", "b"], '
            '"correct_option_index": 0}, '
            '{"question_id": "q2", "prompt": "p2", "options": ["a", "b"], '
            '"correct_option_index": 0}, '
            '{"question_id": "q3", "prompt": "p3", "options": ["a", "b"], '
            '"correct_option_index": 0}]'
        )

    monkeypatch.setattr(
        "app.services.quiz_providers.ollama_provider.generate", fake_generate
    )

    body = "The water cycle includes evaporation, condensation, and precipitation."
    OllamaQuizProvider().generate_quiz("Medium", content_body=body)

    assert len(captured_prompts) == 1
    assert body in captured_prompts[0]


def test_ollama_quiz_provider_raises_on_malformed_json(monkeypatch):
    monkeypatch.setattr(
        "app.services.quiz_providers.ollama_provider.generate",
        lambda prompt: "not json at all {{{",
    )
    with pytest.raises(QuizGenerationError):
        OllamaQuizProvider().generate_quiz("Beginner")


def test_ollama_quiz_provider_raises_on_too_few_questions(monkeypatch):
    """
    A model returning fewer than 3 questions (a weak/small model
    under-delivering on the requested count) must raise
    QuizGenerationError so FallbackQuizProvider substitutes the
    template provider's full-length quiz, rather than silently handing
    the student a too-short quiz.
    """
    too_short = (
        '[{"question_id": "q1", "prompt": "2+2?", "options": ["3", "4"], '
        '"correct_option_index": 1}, '
        '{"question_id": "q2", "prompt": "3+3?", "options": ["5", "6"], '
        '"correct_option_index": 1}]'
    )
    monkeypatch.setattr(
        "app.services.quiz_providers.ollama_provider.generate", lambda prompt: too_short
    )
    with pytest.raises(QuizGenerationError):
        OllamaQuizProvider().generate_quiz("Beginner")


def test_ollama_quiz_provider_raises_on_missing_required_fields(monkeypatch):
    monkeypatch.setattr(
        "app.services.quiz_providers.ollama_provider.generate",
        lambda prompt: '[{"prompt": "missing question_id and options"}]',
    )
    with pytest.raises(QuizGenerationError):
        OllamaQuizProvider().generate_quiz("Beginner")


def test_ollama_quiz_provider_raises_on_out_of_range_correct_index(monkeypatch):
    bad_index_json = (
        '[{"question_id": "q1", "prompt": "2+2?", "options": ["3", "4"], '
        '"correct_option_index": 99}]'
    )
    monkeypatch.setattr(
        "app.services.quiz_providers.ollama_provider.generate", lambda prompt: bad_index_json
    )
    with pytest.raises(QuizGenerationError):
        OllamaQuizProvider().generate_quiz("Beginner")


def test_ollama_quiz_provider_raises_when_client_fails(monkeypatch):
    def _raise(*args, **kwargs):
        raise OllamaGenerationError("simulated client failure")

    monkeypatch.setattr("app.services.quiz_providers.ollama_provider.generate", _raise)
    with pytest.raises(QuizGenerationError):
        OllamaQuizProvider().generate_quiz("Beginner")


# ==========================================================================
# 3. REFLECTION PROVIDER LEVEL — OllamaReflectionProvider
# ==========================================================================


def test_ollama_reflection_provider_returns_cleaned_text(monkeypatch):
    monkeypatch.setattr(
        "app.services.reflection_providers.ollama_provider.generate",
        lambda prompt: "  Great job today!  ",
    )
    result = OllamaReflectionProvider().generate_reflection(
        ReflectionContext(difficulty_level="Beginner")
    )
    assert result.generated_by == "ollama"
    assert result.content == "Great job today!"


def test_ollama_reflection_provider_strips_thinking_block(monkeypatch):
    """
    Regression test: unlike quiz generation (which fails loudly on a
    <think> block because it breaks JSON parsing), a reflection is
    plain text — a leading <think> block here would NOT raise an
    error, it would silently be shown to the student as if it were
    their reflection message. This must be stripped before the
    response is accepted.
    """
    response_with_thinking = (
        "<think>The student did well, I should write something "
        "encouraging about their session.</think>\n"
        "Great job today! You worked hard and it really showed."
    )
    monkeypatch.setattr(
        "app.services.reflection_providers.ollama_provider.generate",
        lambda prompt: response_with_thinking,
    )
    result = OllamaReflectionProvider().generate_reflection(
        ReflectionContext(difficulty_level="Beginner")
    )
    assert result.generated_by == "ollama"
    assert "<think>" not in result.content
    assert result.content == "Great job today! You worked hard and it really showed."


def test_ollama_reflection_provider_raises_on_empty_response(monkeypatch):
    monkeypatch.setattr(
        "app.services.reflection_providers.ollama_provider.generate", lambda prompt: "   "
    )
    with pytest.raises(ReflectionGenerationError):
        OllamaReflectionProvider().generate_reflection(
            ReflectionContext(difficulty_level="Beginner")
        )


def test_ollama_reflection_provider_raises_when_response_is_only_thinking(monkeypatch):
    """
    A response that is ENTIRELY a <think> block with no actual
    reflection content afterward must raise, not return an empty
    string as if it were a valid (if blank) reflection.
    """
    monkeypatch.setattr(
        "app.services.reflection_providers.ollama_provider.generate",
        lambda prompt: "<think>Thinking about what to say...</think>",
    )
    with pytest.raises(ReflectionGenerationError):
        OllamaReflectionProvider().generate_reflection(
            ReflectionContext(difficulty_level="Beginner")
        )


def test_ollama_reflection_provider_raises_when_client_fails(monkeypatch):
    def _raise(*args, **kwargs):
        raise OllamaGenerationError("simulated client failure")

    monkeypatch.setattr("app.services.reflection_providers.ollama_provider.generate", _raise)
    with pytest.raises(ReflectionGenerationError):
        OllamaReflectionProvider().generate_reflection(
            ReflectionContext(difficulty_level="Beginner")
        )


# ==========================================================================
# 4. FALLBACK COMPOSITION — the six required scenarios (A-F), using the
#    codebase's own dependency-injection seam (primary=/fallback=), NOT a
#    monkeypatch of frozen internals.
# ==========================================================================


class _AlwaysSucceedsQuiz(QuizProvider):
    """Stands in for 'Ollama available' (scenario A) — mocked success."""

    def generate_quiz(self, difficulty_level: str, content_body: str | None = None) -> QuizGenerationResult:
        return QuizGenerationResult(
            questions=[
                QuizQuestionInternal(
                    question_id="fake_1", prompt="fake?", options=["a", "b"], correct_option_index=0
                )
            ],
            source="ai_generated",
        )


class _AlwaysFailsQuiz(QuizProvider):
    """Stands in for unavailable/timeout/malformed (scenarios B/C/D) —
    the provider layer collapses all three causes to one exception
    type by design, so one fake covers all three from the fallback
    composition's point of view."""

    def generate_quiz(self, difficulty_level: str, content_body: str | None = None) -> QuizGenerationResult:
        raise QuizGenerationError("simulated failure (stands in for B/C/D)")


def test_fallback_quiz_uses_primary_when_available_scenario_a():
    """Scenario A (mocked): primary succeeds, template is never invoked."""
    provider = FallbackQuizProvider(primary=_AlwaysSucceedsQuiz(), fallback=TemplateQuizProvider())
    result = provider.generate_quiz("Beginner")
    assert result.source == "ai_generated"
    assert result.questions[0].question_id == "fake_1"


def test_fallback_quiz_falls_back_on_primary_failure_scenarios_bcd():
    """Scenarios B/C/D (mocked): primary fails, falls back to the REAL
    TemplateQuizProvider — verifying the fallback output is actually
    produced by the existing template provider, not a stub."""
    provider = FallbackQuizProvider(primary=_AlwaysFailsQuiz(), fallback=TemplateQuizProvider())
    result = provider.generate_quiz("Medium")
    assert result.source == "template_fallback"
    # Must match the real, frozen template bank's Medium question ids.
    assert {q.question_id for q in result.questions} == {"m1", "m2", "m3", "m4", "m5"}


def test_fallback_quiz_template_fallback_scenario_e():
    """Scenario E: fallback quiz generation, exercised directly against
    the real TemplateQuizProvider (not through the composite)."""
    result = TemplateQuizProvider().generate_quiz("Hard")
    assert result.source == "template_fallback"
    assert len(result.questions) == 5
    for q in result.questions:
        assert 0 <= q.correct_option_index < len(q.options)


class _AlwaysSucceedsReflection(ReflectionProvider):
    def generate_reflection(self, context: ReflectionContext) -> ReflectionGenerationResult:
        return ReflectionGenerationResult(content="fake reflection", generated_by="ollama")


class _AlwaysFailsReflection(ReflectionProvider):
    def generate_reflection(self, context: ReflectionContext) -> ReflectionGenerationResult:
        raise ReflectionGenerationError("simulated failure (stands in for B/C/D)")


def test_fallback_reflection_uses_primary_when_available_scenario_a():
    provider = FallbackReflectionProvider(
        primary=_AlwaysSucceedsReflection(), fallback=TemplateReflectionProvider()
    )
    result = provider.generate_reflection(ReflectionContext(difficulty_level="Beginner"))
    assert result.generated_by == "ollama"
    assert result.content == "fake reflection"


def test_fallback_reflection_falls_back_on_primary_failure_scenarios_bcd():
    provider = FallbackReflectionProvider(
        primary=_AlwaysFailsReflection(), fallback=TemplateReflectionProvider()
    )
    result = provider.generate_reflection(
        ReflectionContext(difficulty_level="Medium", quiz_score=90.0)
    )
    assert result.generated_by == "template"
    assert "Great work" in result.content  # real template branch for score >= 80


def test_fallback_reflection_template_fallback_scenario_f():
    """Scenario F: fallback reflection generation, exercised directly
    against the real TemplateReflectionProvider."""
    result = TemplateReflectionProvider().generate_reflection(
        ReflectionContext(difficulty_level="Easy", quiz_score=40.0)
    )
    assert result.generated_by == "template"
    assert len(result.content) > 0


def test_both_primary_and_template_fallback_failing_does_not_leak_raw_exception():
    """
    Defensive/hypothetical test: the real TemplateProvider always
    succeeds by design (no I/O, static lookup), so this scenario can't
    occur in production. It's included only to confirm that IF a
    fallback provider were ever swapped for one that also fails, the
    resulting exception is still a plain provider-level exception type
    (not something that would leak framework/library internals) — using
    dependency injection only, no frozen code modified.
    """

    class _AlsoFailsQuiz(QuizProvider):
        def generate_quiz(self, difficulty_level: str, content_body: str | None = None) -> QuizGenerationResult:
            raise QuizGenerationError("fallback also failed (hypothetical)")

    provider = FallbackQuizProvider(primary=_AlwaysFailsQuiz(), fallback=_AlsoFailsQuiz())
    with pytest.raises(QuizGenerationError) as excinfo:
        provider.generate_quiz("Beginner")
    # The exception is exactly this module's own type, not some deeper
    # library exception bubbling up unwrapped.
    assert isinstance(excinfo.value, QuizGenerationError)


# ==========================================================================
# 5. LIVE HTTP CONFIRMATION — real fallback behavior in THIS environment
#    (claim #1 in the module docstring: no mocking here at all).
# ==========================================================================


def test_live_quiz_generation_uses_fallback_in_this_environment(
    client, student_token, seeded_session
):
    """
    No mocking. This hits the real, wired-in _ACTIVE_PROVIDER through
    the actual HTTP endpoint. Because no Ollama server is reachable in
    this test environment, this is a live, unmocked confirmation that
    the fallback path is what students actually experience here —
    consistent with what Ticket D's manual testing already found.
    """
    response = client.post(
        f"/quiz-attempts/start/{seeded_session['id']}", headers=auth_header(student_token)
    )
    assert response.status_code == 201
    assert response.json()["quiz_source"] == "template_fallback"


def test_live_reflection_generation_uses_fallback_in_this_environment(
    client, student_token, seeded_session
):
    response = client.post(
        f"/learning-reflections/generate/{seeded_session['id']}",
        headers=auth_header(student_token),
    )
    assert response.status_code == 201
    assert response.json()["generated_by"] == "template"
