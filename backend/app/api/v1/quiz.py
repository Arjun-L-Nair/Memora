"""
api/v1/quiz.py

Quiz Attempt router (Master Specification Section 6, 7, 10).

Two access patterns on one resource:
    - Students (get_current_student, frozen Phase 4) start, view, and
      submit quiz attempts for their OWN learning sessions.
    - Teachers (get_current_teacher, frozen Phase 4) may only READ quiz
      attempts belonging to sessions under their own learning plans —
      there is no teacher write path, since quizzes are never
      teacher-authored (see Phase 8 architecture revision).

Lifecycle: CREATED -> SUBMITTED -> LOCKED. A second submission returns
409, per the confirmed Phase 8 policy (spec is silent; this is the
approved, explicit policy).

This router contains no business logic or database access; it only
parses requests, calls app.services.quiz_service, translates
service-layer exceptions into HTTP responses, and returns schemas.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_student, get_current_teacher
from app.database import get_db
from app.models import Student, Teacher
from app.schemas.quiz_attempt import (
    HintResponse,
    QuizAttemptResponse,
    QuizReviewResponse,
    QuizSubmitRequest,
)
from app.services.quiz_service import (
    InvalidSessionStateForQuizError,
    LearningSessionNotFoundError,
    QuestionNotFoundError,
    QuizAttemptAlreadyExistsError,
    QuizAttemptAlreadySubmittedError,
    QuizAttemptNotFoundError,
    QuizAttemptNotSubmittedError,
    get_hint_for_question,
    get_quiz_attempt_by_session_for_student,
    get_quiz_attempt_for_student,
    get_quiz_attempt_for_teacher,
    get_quiz_review_for_student,
    start_quiz_attempt,
    submit_quiz_attempt,
    to_response,
)

router = APIRouter(prefix="/quiz-attempts", tags=["Quiz"])

_SESSION_NOT_FOUND = HTTPException(
    status_code=status.HTTP_404_NOT_FOUND,
    detail="Learning session not found.",
)
_QUIZ_NOT_FOUND = HTTPException(
    status_code=status.HTTP_404_NOT_FOUND,
    detail="Quiz attempt not found.",
)


@router.post(
    "/start/{learning_session_id}",
    response_model=QuizAttemptResponse,
    status_code=status.HTTP_201_CREATED,
)
def start_quiz_attempt_endpoint(
    learning_session_id: int,
    student: Student = Depends(get_current_student),
    db: Session = Depends(get_db),
) -> QuizAttemptResponse:
    """
    Start a new quiz attempt for one of the student's own sessions.
    The active quiz provider (template-based fallback in this phase)
    generates the questions exactly once, at creation time.
    """
    try:
        attempt = start_quiz_attempt(db, student.id, learning_session_id)
    except LearningSessionNotFoundError:
        raise _SESSION_NOT_FOUND
    except InvalidSessionStateForQuizError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        )
    except QuizAttemptAlreadyExistsError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        )

    return to_response(attempt)


@router.get(
    "/by-session/{learning_session_id}",
    response_model=QuizAttemptResponse | None,
)
def get_quiz_attempt_by_session_endpoint(
    learning_session_id: int,
    student: Student = Depends(get_current_student),
    db: Session = Depends(get_db),
) -> QuizAttemptResponse | None:
    """
    Look up the quiz attempt (if any) already belonging to one of the
    student's own sessions, without attempting to create one. Returns
    null when no attempt has been started yet — this lets the frontend
    resume an existing attempt (in progress or submitted) instead of
    treating a second "start" call's 409 as a dead end.
    """
    try:
        attempt = get_quiz_attempt_by_session_for_student(db, student.id, learning_session_id)
    except LearningSessionNotFoundError:
        raise _SESSION_NOT_FOUND

    return to_response(attempt) if attempt is not None else None


@router.get("/{quiz_attempt_id}", response_model=QuizAttemptResponse)
def get_quiz_attempt_as_student_endpoint(
    quiz_attempt_id: int,
    student: Student = Depends(get_current_student),
    db: Session = Depends(get_db),
) -> QuizAttemptResponse:
    """Get a quiz attempt owned by the authenticated student."""
    try:
        attempt = get_quiz_attempt_for_student(db, student.id, quiz_attempt_id)
    except QuizAttemptNotFoundError:
        raise _QUIZ_NOT_FOUND

    return to_response(attempt)


@router.get("/{quiz_attempt_id}/review", response_model=QuizReviewResponse)
def get_quiz_review_endpoint(
    quiz_attempt_id: int,
    student: Student = Depends(get_current_student),
    db: Session = Depends(get_db),
) -> QuizReviewResponse:
    """
    Full per-question review for one of the student's own quiz
    attempts, ONLY once it has been submitted — for each question,
    what the correct answer was, what the student actually picked,
    and whether that was right. Returns 409 if the attempt hasn't been
    submitted yet (the answer key stays server-only until then).
    """
    try:
        return get_quiz_review_for_student(db, student.id, quiz_attempt_id)
    except QuizAttemptNotFoundError:
        raise _QUIZ_NOT_FOUND
    except QuizAttemptNotSubmittedError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        )


@router.post("/{quiz_attempt_id}/submit", response_model=QuizAttemptResponse)
def submit_quiz_attempt_endpoint(
    quiz_attempt_id: int,
    payload: QuizSubmitRequest,
    student: Student = Depends(get_current_student),
    db: Session = Depends(get_db),
) -> QuizAttemptResponse:
    """
    Submit and grade a quiz attempt. Grading uses only the persisted
    questions_json — the quiz provider is never called here. Returns
    409 if the attempt has already been submitted (locked).
    """
    try:
        attempt = submit_quiz_attempt(db, student.id, quiz_attempt_id, payload)
    except QuizAttemptNotFoundError:
        raise _QUIZ_NOT_FOUND
    except QuizAttemptAlreadySubmittedError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        )

    return to_response(attempt)


@router.get("/{quiz_attempt_id}/hint/{question_id}", response_model=HintResponse)
def get_hint_endpoint(
    quiz_attempt_id: int,
    question_id: str,
    student: Student = Depends(get_current_student),
    db: Session = Depends(get_db),
) -> HintResponse:
    """
    Get an "eliminate one wrong answer" hint for a specific question in
    an in-progress (not yet submitted) quiz attempt. Returns the index
    of one guaranteed-wrong option to grey out client-side — the
    correct answer itself is never revealed or returned.

    Returns 409 if the attempt has already been submitted (hints are
    only meaningful before answering is locked in).
    """
    try:
        eliminated_index = get_hint_for_question(
            db, student.id, quiz_attempt_id, question_id
        )
    except QuizAttemptNotFoundError:
        raise _QUIZ_NOT_FOUND
    except QuestionNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Question '{question_id}' not found in this quiz attempt.",
        )
    except QuizAttemptAlreadySubmittedError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        )

    return HintResponse(question_id=question_id, eliminated_option_index=eliminated_index)


@router.get("/teacher/{quiz_attempt_id}", response_model=QuizAttemptResponse)
def get_quiz_attempt_as_teacher_endpoint(
    quiz_attempt_id: int,
    teacher: Teacher = Depends(get_current_teacher),
    db: Session = Depends(get_db),
) -> QuizAttemptResponse:
    """
    Get a quiz attempt belonging to a session under one of the
    authenticated teacher's own learning plans. Read-only.
    """
    try:
        attempt = get_quiz_attempt_for_teacher(db, teacher.id, quiz_attempt_id)
    except QuizAttemptNotFoundError:
        raise _QUIZ_NOT_FOUND

    return to_response(attempt)
