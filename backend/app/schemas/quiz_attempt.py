"""
schemas/quiz_attempt.py

Pydantic schemas for Quiz Attempts (Master Specification Section 6, 7,
10: Quiz, LLM Reliability).

QuizAttempt.questions_json stores serialized structured question data.
These schemas define that structure explicitly rather than exposing a
raw JSON string anywhere in the API.

QuizQuestionOut deliberately excludes the correct answer — it is the
shape returned to a student for a quiz they have not yet (or have just)
completed. The answer key never leaves the server.

No teacher-authored quiz-creation schema exists here (see Phase 8
architecture revision): a QuizAttempt's questions are produced
automatically by a quiz provider (TemplateQuizProvider for this phase;
an OllamaQuizProvider later), never entered manually by a teacher.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class QuizQuestionOut(BaseModel):
    """
    A single quiz question as shown to the student. Never includes the
    correct answer.
    """

    question_id: str
    prompt: str
    options: list[str]


class HintResponse(BaseModel):
    """
    Response body for GET /quiz-attempts/{id}/hint/{question_id}.

    eliminated_option_index identifies ONE guaranteed-wrong option the
    frontend should grey out/disable, WITHOUT revealing which of the
    remaining options is correct (the answer key stays server-only —
    see QuizQuestionOut above). -1 in the rare case no wrong option
    could be identified (a malformed single-option question); the
    frontend should treat that as "no hint available" and not disable
    anything.
    """

    question_id: str
    eliminated_option_index: int


class QuizAnswerSubmit(BaseModel):
    """A single answer submitted by the student for one question."""

    question_id: str
    selected_option_index: int = Field(..., ge=0)
    hint_used: bool = Field(
        default=False,
        description=(
            "Whether the student used the 'eliminate one wrong answer' "
            "hint for this specific question. Summed across all answers "
            "in a submission to populate LearningSession.hint_usage_count "
            "— hint-seeking behaviour is one of the engagement signals "
            "the spec explicitly calls out (Section 7), so this is real "
            "measured data, not a synthetic/demo-only value."
        ),
    )


class QuizSubmitRequest(BaseModel):
    """Request body for POST /quiz-attempts/{id}/submit."""

    answers: list[QuizAnswerSubmit] = Field(..., min_length=1)
    time_taken_seconds: int | None = Field(default=None, ge=0)


class QuizAttemptResponse(BaseModel):
    """
    Response body for all quiz attempt endpoints.

    questions is always the answer-free QuizQuestionOut shape. score/
    accuracy/submitted_at are null until the student submits.
    """

    model_config = ConfigDict(from_attributes=True)

    id: int
    learning_session_id: int
    quiz_source: str
    difficulty_level: str
    total_questions: int
    questions: list[QuizQuestionOut]
    score: float | None
    accuracy: float | None
    time_taken_seconds: int | None
    submitted_at: datetime | None


class QuizReviewQuestion(BaseModel):
    """
    One question's full review detail — ONLY ever returned for an
    already-submitted attempt (see get_quiz_review_for_student's
    QuizAttemptNotSubmittedError). Unlike QuizQuestionOut, this
    intentionally DOES include the correct answer, since the quiz is
    already graded and locked by the time this is reachable — there
    is nothing left to protect by hiding it, and a student reviewing
    their own completed quiz needs to see what the right answer was
    for each question they got wrong.
    """

    question_id: str
    prompt: str
    options: list[str]
    correct_option_index: int
    selected_option_index: int | None
    is_correct: bool


class QuizReviewResponse(BaseModel):
    """Response body for GET /quiz-attempts/{id}/review."""

    id: int
    score: float
    accuracy: float
    total_questions: int
    questions: list[QuizReviewQuestion]
