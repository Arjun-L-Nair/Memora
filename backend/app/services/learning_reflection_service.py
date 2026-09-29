"""
services/learning_reflection_service.py

Business logic for Learning Reflections (Master Specification Section
5, 6, 7, 10).

Student-triggered, mirroring Quiz's ownership pattern (Phase 8) rather
than the teacher-triggered pattern used for Engagement
Prediction/Adaptive Suggestions (Phases 9-10) — the spec's Core User
Journey ("Today's Learning -> ... -> Learning Reflection -> Progress
Saved") places Reflection within the student's own session flow.

Reuses _get_owned_session_for_student() and LearningSessionNotFoundError
directly from quiz_service.py rather than duplicating the ownership
check.

Exactly one LearningReflection per LearningSession (enforced by the
frozen unique=True constraint on learning_session_id) — generating a
second time raises LearningReflectionAlreadyExistsError, matching the
CREATED -> LOCKED pattern already used for QuizAttempt and
EngagementPrediction.

Calls the active (fallback-wrapped) ReflectionProvider exactly once;
this service has no knowledge of Ollama, templates, or HTTP — all of
that is hidden behind the provider interface.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session as DBSession

from app.models import EngagementPrediction, LearningReflection, LearningSession, QuizAttempt
from app.services.quiz_service import (
    LearningSessionNotFoundError,
    _get_owned_session_for_student,
)
from app.services.reflection_providers.base import ReflectionContext
from app.services.reflection_providers.fallback_provider import FallbackReflectionProvider

__all__ = [
    "LearningSessionNotFoundError",
    "LearningReflectionAlreadyExistsError",
    "LearningReflectionNotFoundError",
    "generate_learning_reflection",
    "get_learning_reflection_for_student",
]

# The single active provider for this phase — Ollama first, template
# fallback on any failure. Swapping providers later means changing
# only this line; nothing below it needs to change.
_ACTIVE_PROVIDER = FallbackReflectionProvider()


class LearningReflectionAlreadyExistsError(Exception):
    """Raised when attempting to generate a reflection for a session that already has one."""


class LearningReflectionNotFoundError(Exception):
    """Raised when a reflection does not exist, or does not belong to the requesting student."""


def _build_context(db: DBSession, session_id: int, difficulty_level: str) -> ReflectionContext:
    """
    Gather already-available data for this session into a
    ReflectionContext. quiz_score/accuracy and engagement_label are
    populated only if a QuizAttempt / EngagementPrediction already
    exists for this session — both are optional, exactly as with
    Engagement Prediction's own feature extraction (Phase 9).
    """
    quiz_attempt = db.execute(
        select(QuizAttempt).where(QuizAttempt.learning_session_id == session_id)
    ).scalar_one_or_none()

    prediction = db.execute(
        select(EngagementPrediction).where(
            EngagementPrediction.learning_session_id == session_id
        )
    ).scalar_one_or_none()

    return ReflectionContext(
        difficulty_level=difficulty_level,
        quiz_score=quiz_attempt.score if quiz_attempt is not None else None,
        quiz_accuracy=quiz_attempt.accuracy if quiz_attempt is not None else None,
        engagement_label=prediction.engagement_label if prediction is not None else None,
    )


def generate_learning_reflection(
    db: DBSession, student_id: int, learning_session_id: int
) -> LearningReflection:
    """
    Generate and persist a new reflection for one of the student's own
    sessions.

    Raises:
        LearningSessionNotFoundError: session doesn't exist or isn't
            owned by this student.
        LearningReflectionAlreadyExistsError: a reflection already
            exists for this session.
    """
    session = _get_owned_session_for_student(db, student_id, learning_session_id)

    existing = db.execute(
        select(LearningReflection).where(
            LearningReflection.learning_session_id == learning_session_id
        )
    ).scalar_one_or_none()
    if existing is not None:
        raise LearningReflectionAlreadyExistsError(
            f"A learning reflection already exists for session {learning_session_id}."
        )

    context = _build_context(db, learning_session_id, session.difficulty_level_at_session)

    # The ONLY call into the provider layer — this service has no
    # knowledge of Ollama, templates, or prompt construction.
    result = _ACTIVE_PROVIDER.generate_reflection(context)

    reflection = LearningReflection(
        learning_session_id=learning_session_id,
        content=result.content,
        generated_by=result.generated_by,
    )
    db.add(reflection)
    db.commit()
    db.refresh(reflection)
    return reflection


def get_learning_reflection_by_session_for_student(
    db: DBSession, student_id: int, learning_session_id: int
) -> LearningReflection | None:
    """
    Get the reflection (if any) already belonging to one of the
    student's own sessions. Returns None rather than raising when no
    reflection exists yet — this is the normal "not generated yet"
    state, not an error, and lets the frontend resume an existing
    reflection instead of treating generate_learning_reflection()'s 409
    as a dead end.
    """
    session = _get_owned_session_for_student(db, student_id, learning_session_id)

    return db.execute(
        select(LearningReflection).where(
            LearningReflection.learning_session_id == session.id
        )
    ).scalar_one_or_none()


def get_learning_reflection_for_student(
    db: DBSession, student_id: int, reflection_id: int
) -> LearningReflection:
    """
    Get a single reflection by id, scoped to the requesting student via
    its session's ownership.
    """
    reflection = db.execute(
        select(LearningReflection)
        .join(LearningSession, LearningReflection.learning_session_id == LearningSession.id)
        .where(
            LearningReflection.id == reflection_id,
            LearningSession.student_id == student_id,
        )
    ).scalar_one_or_none()

    if reflection is None:
        raise LearningReflectionNotFoundError(
            f"Learning reflection {reflection_id} not found."
        )

    return reflection
