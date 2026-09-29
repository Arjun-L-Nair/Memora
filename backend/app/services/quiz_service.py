"""
services/quiz_service.py

Business logic for Quiz Attempts (Master Specification Section 6, 7, 10).

Quiz creation vs. grading — critical architectural boundary:
    - start_quiz_attempt() calls the active QuizProvider EXACTLY ONCE,
      at creation time, and persists the result into
      QuizAttempt.questions_json.
    - submit_quiz_attempt() NEVER calls the provider. It reads only the
      already-persisted questions_json as the sole source of truth for
      questions, correct answers, and scoring. This guarantees a quiz
      attempt is graded against exactly what was shown to the student,
      regardless of what the currently-active provider would produce if
      called again (e.g. after a provider swap to Ollama in a future
      phase).

Ownership:
    - A student may only start/view/submit a quiz attempt for their OWN
      learning session (LearningSession.student_id == the student).
    - A teacher may only view a quiz attempt whose session belongs to
      one of their own learning plans (same ownership chain used
      throughout Phase 6/7).

No teacher-authored quiz creation exists (see Phase 8 architecture
revision) — quizzes are always produced automatically by the active
provider when a student starts one.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session as DBSession

from app.models import LearningPlan, LearningSession, QuizAttempt
from app.schemas.quiz_attempt import (
    QuizAttemptResponse,
    QuizQuestionOut,
    QuizReviewQuestion,
    QuizReviewResponse,
    QuizSubmitRequest,
)
from app.services.quiz_providers.base import QuizProvider, QuizQuestionInternal
from app.services.quiz_providers.fallback_provider import FallbackQuizProvider

# The single active provider for this phase. Now the fallback-wrapped
# chain (Ollama first, template on any failure) rather than the
# template provider alone — this is the ONLY line that changed in this
# file for Phase 11; every function below is untouched.
_ACTIVE_PROVIDER: QuizProvider = FallbackQuizProvider()


class LearningSessionNotFoundError(Exception):
    """Raised when a session does not exist, or does not belong to the requesting user."""


class QuizAttemptNotFoundError(Exception):
    """Raised when a quiz attempt does not exist, or does not belong to the requesting user."""


class QuizAttemptAlreadyExistsError(Exception):
    """Raised when attempting to start a quiz for a session that already has one."""


class QuizAttemptAlreadySubmittedError(Exception):
    """Raised when attempting to submit a quiz attempt that has already been graded."""


class InvalidSessionStateForQuizError(Exception):
    """Raised when attempting to start a quiz for a session that is not currently 'started'."""


class QuestionNotFoundError(Exception):
    """Raised when a hint is requested for a question_id that doesn't exist in this attempt."""


class QuizAttemptNotSubmittedError(Exception):
    """Raised when a review is requested for an attempt that hasn't been submitted/graded yet."""


def _get_owned_session_for_student(
    db: DBSession, student_id: int, session_id: int
) -> LearningSession:
    """Confirm a session exists and belongs to the given student."""
    session = db.execute(
        select(LearningSession).where(
            LearningSession.id == session_id,
            LearningSession.student_id == student_id,
        )
    ).scalar_one_or_none()

    if session is None:
        raise LearningSessionNotFoundError(f"Learning session {session_id} not found.")

    return session


def _serialize_questions(questions: list[QuizQuestionInternal]) -> str:
    """Serialize internal (answer-including) questions for storage."""
    return json.dumps([q.model_dump() for q in questions])


def _deserialize_questions(questions_json: str) -> list[QuizQuestionInternal]:
    """Deserialize the persisted questions_json back into internal form."""
    raw = json.loads(questions_json)
    return [QuizQuestionInternal.model_validate(item) for item in raw]


def start_quiz_attempt(
    db: DBSession, student_id: int, learning_session_id: int
) -> QuizAttempt:
    """
    Start a new quiz attempt for one of the student's own sessions.

    Calls the active QuizProvider exactly once to produce questions,
    then persists them. Raises:
        LearningSessionNotFoundError: session doesn't exist or isn't owned.
        InvalidSessionStateForQuizError: session is not "started".
        QuizAttemptAlreadyExistsError: a quiz already exists for this session.
    """
    session = _get_owned_session_for_student(db, student_id, learning_session_id)

    if session.status != "started":
        raise InvalidSessionStateForQuizError(
            f"Session {learning_session_id} is '{session.status}', not 'started'."
        )

    existing = db.execute(
        select(QuizAttempt).where(
            QuizAttempt.learning_session_id == learning_session_id
        )
    ).scalar_one_or_none()
    if existing is not None:
        raise QuizAttemptAlreadyExistsError(
            f"A quiz attempt already exists for session {learning_session_id}."
        )

    # Fetch the content body associated with this session so the template
    # provider can generate contextually relevant questions. LearningSession
    # always has a learning_content_id (NOT NULL FK), so this lookup is safe.
    from app.models.learning_content import LearningContent as LearningContentModel
    content = db.get(LearningContentModel, session.learning_content_id)
    content_body = content.body if content is not None else None

    # Use the CONTENT's own difficulty_level (what the teacher actually
    # set when authoring this lesson) to drive quiz generation and the
    # displayed difficulty — NOT session.difficulty_level_at_session.
    # That field is a snapshot of the STUDENT's adaptive level (which
    # starts at "Beginner" for every new student and only changes via
    # the engagement-based auto-adjustment engine), and using it here
    # meant a teacher's chosen content difficulty had zero effect on
    # quiz generation or the difficulty badge shown to the student —
    # every quiz for a new/unadjusted student silently generated at
    # "Beginner" regardless of what the content was actually tagged.
    # session.difficulty_level_at_session remains exactly what it was
    # for content RECOMMENDATION (matching level to a student when
    # picking what to serve next) and for the adaptive engine's future
    # adjustments — this fix only changes which signal drives the quiz
    # for content that has ALREADY been selected, where the content's
    # own authored difficulty is the more specific, more correct value.
    quiz_difficulty_level = content.difficulty_level if content is not None else session.difficulty_level_at_session

    result = _ACTIVE_PROVIDER.generate_quiz(
        quiz_difficulty_level,
        content_body=content_body,
    )

    attempt = QuizAttempt(
        learning_session_id=learning_session_id,
        quiz_source=result.source,
        questions_json=_serialize_questions(result.questions),
        difficulty_level=quiz_difficulty_level,
        total_questions=len(result.questions),
    )
    db.add(attempt)
    db.commit()
    db.refresh(attempt)
    return attempt


def get_quiz_attempt_by_session_for_student(
    db: DBSession, student_id: int, learning_session_id: int
) -> QuizAttempt | None:
    """
    Get the quiz attempt (if any) already belonging to one of the
    student's own sessions. Returns None rather than raising when no
    attempt exists yet — this is the normal "not started yet" state,
    not an error, and lets the frontend decide whether to resume an
    existing attempt or start a new one without relying on a 409 from
    start_quiz_attempt() as its only signal.

    Ownership is enforced the same way as everywhere else in this
    module: only a session belonging to the requesting student is
    considered.
    """
    session = db.execute(
        select(LearningSession).where(
            LearningSession.id == learning_session_id,
            LearningSession.student_id == student_id,
        )
    ).scalar_one_or_none()

    if session is None:
        raise LearningSessionNotFoundError(f"Learning session {learning_session_id} not found.")

    return db.execute(
        select(QuizAttempt).where(
            QuizAttempt.learning_session_id == learning_session_id
        )
    ).scalar_one_or_none()


def get_quiz_attempt_for_student(
    db: DBSession, student_id: int, quiz_attempt_id: int
) -> QuizAttempt:
    """
    Get a quiz attempt by id, scoped to the requesting student via its
    session's ownership.
    """
    attempt = db.execute(
        select(QuizAttempt)
        .join(LearningSession)
        .where(
            QuizAttempt.id == quiz_attempt_id,
            LearningSession.student_id == student_id,
        )
    ).scalar_one_or_none()

    if attempt is None:
        raise QuizAttemptNotFoundError(f"Quiz attempt {quiz_attempt_id} not found.")

    return attempt


def get_quiz_review_for_student(
    db: DBSession, student_id: int, quiz_attempt_id: int
) -> QuizReviewResponse:
    """
    Full per-question review (prompt, options, correct answer, the
    student's own selected answer, and whether it was correct) for one
    of the student's own quiz attempts — ONLY once that attempt has
    been submitted and graded.

    Raises:
        QuizAttemptNotFoundError: attempt doesn't exist or isn't owned.
        QuizAttemptNotSubmittedError: attempt exists but hasn't been
            submitted yet — the answer key stays server-only until
            then (same invariant QuizQuestionOut enforces elsewhere in
            this module; this function is the one deliberate,
            narrowly-scoped exception to it, gated strictly on
            submitted_at being set).
    """
    attempt = get_quiz_attempt_for_student(db, student_id, quiz_attempt_id)

    if attempt.submitted_at is None:
        raise QuizAttemptNotSubmittedError(
            f"Quiz attempt {quiz_attempt_id} has not been submitted yet."
        )

    questions = _deserialize_questions(attempt.questions_json)
    submitted_answers = (
        {a["question_id"]: a["selected_option_index"] for a in json.loads(attempt.answers_json)}
        if attempt.answers_json
        else {}
    )

    review_questions = [
        QuizReviewQuestion(
            question_id=q.question_id,
            prompt=q.prompt,
            options=q.options,
            correct_option_index=q.correct_option_index,
            selected_option_index=submitted_answers.get(q.question_id),
            is_correct=submitted_answers.get(q.question_id) == q.correct_option_index,
        )
        for q in questions
    ]

    return QuizReviewResponse(
        id=attempt.id,
        score=attempt.score or 0.0,
        accuracy=attempt.accuracy or 0.0,
        total_questions=attempt.total_questions,
        questions=review_questions,
    )


def get_quiz_attempt_for_teacher(
    db: DBSession, teacher_id: int, quiz_attempt_id: int
) -> QuizAttempt:
    """
    Get a quiz attempt by id, scoped to the requesting teacher via its
    session's plan ownership.
    """
    attempt = db.execute(
        select(QuizAttempt)
        .join(LearningSession)
        .join(LearningPlan)
        .where(
            QuizAttempt.id == quiz_attempt_id,
            LearningPlan.teacher_id == teacher_id,
        )
    ).scalar_one_or_none()

    if attempt is None:
        raise QuizAttemptNotFoundError(f"Quiz attempt {quiz_attempt_id} not found.")

    return attempt


def submit_quiz_attempt(
    db: DBSession, student_id: int, quiz_attempt_id: int, payload: QuizSubmitRequest
) -> QuizAttempt:
    """
    Grade and submit a quiz attempt.

    Grades ONLY against the already-persisted questions_json — the
    provider is never called here. Raises:
        QuizAttemptNotFoundError: attempt doesn't exist or isn't owned.
        QuizAttemptAlreadySubmittedError: attempt was already graded.
    """
    attempt = get_quiz_attempt_for_student(db, student_id, quiz_attempt_id)

    if attempt.submitted_at is not None:
        raise QuizAttemptAlreadySubmittedError(
            f"Quiz attempt {quiz_attempt_id} has already been submitted."
        )

    # The persisted questions_json is the sole source of truth for
    # correct answers — this is the only place they are read from.
    questions = _deserialize_questions(attempt.questions_json)
    correct_by_id = {q.question_id: q.correct_option_index for q in questions}

    submitted_by_id = {a.question_id: a.selected_option_index for a in payload.answers}

    correct_count = sum(
        1
        for question_id, correct_index in correct_by_id.items()
        if submitted_by_id.get(question_id) == correct_index
    )
    total = len(correct_by_id)
    accuracy = correct_count / total if total > 0 else 0.0
    score = accuracy * 100

    attempt.answers_json = json.dumps(
        [a.model_dump() for a in payload.answers]
    )
    attempt.score = score
    attempt.accuracy = accuracy
    attempt.time_taken_seconds = payload.time_taken_seconds
    attempt.submitted_at = datetime.now(timezone.utc)

    # Real, measured hint-seeking behaviour (Master Specification
    # Section 7 explicitly names hint usage as an engagement
    # indicator). This was previously a database column with nothing
    # anywhere actually populating it from real student sessions —
    # every genuine session persisted hint_usage_count as NULL, so the
    # engagement-prediction model only ever saw real hint data in the
    # synthetic seed dataset, never from an actual student. Writing it
    # here, at submit time, is the natural point: hints are used
    # per-question during the quiz, and submission is when we know the
    # final count for this attempt.
    hint_count = sum(1 for a in payload.answers if a.hint_used)
    session = db.get(LearningSession, attempt.learning_session_id)
    if session is not None:
        # Additive, not overwritten: a session's hint_usage_count
        # should reflect hints used across its whole lifecycle (in
        # case this model is ever extended to multiple quiz attempts
        # per session in the future). Since exactly one quiz attempt
        # exists per session today, this is equivalent to a direct
        # assignment, but written additively so it stays correct if
        # that assumption ever changes.
        session.hint_usage_count = (session.hint_usage_count or 0) + hint_count

    db.commit()
    db.refresh(attempt)
    return attempt


def get_hint_for_question(
    db: DBSession, student_id: int, quiz_attempt_id: int, question_id: str
) -> int:
    """
    Return the index of ONE guaranteed-wrong option for the given
    question, so the frontend can grey it out ("eliminate one wrong
    answer" hint) without ever receiving the correct answer itself.

    This exists as a server-side endpoint specifically because
    QuizQuestionOut (the shape returned to students) never includes
    correct_option_index — the answer key is intentionally
    server-only. A hint that eliminates a wrong option therefore
    cannot be computed client-side without leaking that boundary; the
    server must be the one to pick a safe-to-reveal wrong index.

    Deterministic choice: always returns the wrong option with the
    lowest index (skipping the correct one). This keeps behaviour
    predictable and explainable — the same question always eliminates
    the same option — consistent with the project's broader "AI should
    never make random decisions" principle applied here to hints too,
    which also matters for a population that benefits from
    predictability more than most.

    Does not mutate the attempt or increment any counter — the actual
    hint_usage_count is recorded at submit time (QuizAnswerSubmit.hint_used),
    driven by what the student actually reports using, not by how many
    times this lookup endpoint was called (a student could otherwise
    inflate the count by re-requesting a hint they already have without
    it reflecting genuine additional hint-seeking behaviour).

    Raises QuizAttemptNotFoundError, QuizAttemptAlreadySubmittedError,
    or QuestionNotFoundError.
    """
    attempt = get_quiz_attempt_for_student(db, student_id, quiz_attempt_id)

    if attempt.submitted_at is not None:
        raise QuizAttemptAlreadySubmittedError(
            f"Quiz attempt {quiz_attempt_id} has already been submitted."
        )

    questions = _deserialize_questions(attempt.questions_json)
    question = next((q for q in questions if q.question_id == question_id), None)
    if question is None:
        raise QuestionNotFoundError(
            f"Question '{question_id}' not found in attempt {quiz_attempt_id}."
        )

    for index in range(len(question.options)):
        if index != question.correct_option_index:
            return index

    # Defensive fallback: a single-option question has no wrong answer
    # to eliminate. QuizQuestionInternal requires min_length=2, so this
    # should be unreachable, but returning -1 (an invalid index the
    # frontend can safely ignore) is safer than raising for a hint —
    # a broken hint should never block the student from taking the quiz.
    return -1


def to_response(attempt: QuizAttempt) -> QuizAttemptResponse:
    """
    Build the public, answer-free response shape for a quiz attempt.
    Shared by both student and teacher read paths, and by create/submit
    endpoints, so this parsing logic exists in exactly one place.
    """
    questions = _deserialize_questions(attempt.questions_json)
    public_questions = [
        QuizQuestionOut(
            question_id=q.question_id, prompt=q.prompt, options=q.options
        )
        for q in questions
    ]

    return QuizAttemptResponse(
        id=attempt.id,
        learning_session_id=attempt.learning_session_id,
        quiz_source=attempt.quiz_source,
        difficulty_level=attempt.difficulty_level,
        total_questions=attempt.total_questions,
        questions=public_questions,
        score=attempt.score,
        accuracy=attempt.accuracy,
        time_taken_seconds=attempt.time_taken_seconds,
        submitted_at=attempt.submitted_at,
    )
