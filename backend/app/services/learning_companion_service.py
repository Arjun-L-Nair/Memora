"""
services/learning_companion_service.py

Business logic for Mira, the student learning companion (Memora
overhaul, Component 2).

Now stateful: every student/Mira turn is persisted to
ConversationHistory, and the last 20 turns are sent back to the
provider as a sliding-window context (see CompanionContext.
conversation_history). Detected emotion (ml/emotion_classifier.py) is
stored alongside the student's turn and also logged to EmotionLog so
mood trends are queryable independently of the chat transcript.

Context is built from the student's most recent LearningSession and
its associated QuizAttempt / EngagementPrediction (if any exist), plus
SensoryProfile, mirroring the original stateless version's pattern for
those fields exactly.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session as DBSession

from app.ml.emotion_classifier import classify_emotion
from app.models import (
    ConversationHistory,
    EmotionLog,
    EngagementPrediction,
    LearningSession,
    QuizAttempt,
    SensoryProfile,
    Student,
)
from app.services.companion_providers.base import CompanionContext, CompanionGenerationResult
from app.services.companion_providers.fallback_provider import FallbackCompanionProvider
from app.services.student_service import StudentNotFoundError

__all__ = [
    "StudentNotFoundError",
    "generate_companion_message",
    "get_conversation_history",
]

# The single active provider - Gemini first, Ollama (if enabled) then
# template fallback. Swapping providers later means changing only
# this line.
_ACTIVE_PROVIDER = FallbackCompanionProvider()

_HISTORY_WINDOW = 20


def _build_context(
    db: DBSession,
    student: Student,
    student_message: str | None,
    detected_emotion: str | None,
    interaction_mode: str,
) -> CompanionContext:
    """
    Gather already-available data for this student into a
    CompanionContext, including the sliding window of prior turns.
    """
    recent_session = db.execute(
        select(LearningSession)
        .where(LearningSession.student_id == student.id)
        .order_by(LearningSession.started_at.desc())
        .limit(1)
    ).scalar_one_or_none()

    recent_quiz_score: float | None = None
    recent_engagement_label: str | None = None

    if recent_session is not None:
        quiz_attempt = db.execute(
            select(QuizAttempt).where(QuizAttempt.learning_session_id == recent_session.id)
        ).scalar_one_or_none()
        if quiz_attempt is not None:
            recent_quiz_score = quiz_attempt.score

        prediction = db.execute(
            select(EngagementPrediction).where(
                EngagementPrediction.learning_session_id == recent_session.id
            )
        ).scalar_one_or_none()
        if prediction is not None:
            recent_engagement_label = prediction.engagement_label

    sensory_profile = db.execute(
        select(SensoryProfile).where(SensoryProfile.student_id == student.id)
    ).scalar_one_or_none()

    prior_turns = (
        db.execute(
            select(ConversationHistory)
            .where(ConversationHistory.student_id == student.id)
            .order_by(ConversationHistory.created_at.desc())
            .limit(_HISTORY_WINDOW)
        )
        .scalars()
        .all()
    )
    conversation_history = [
        {"role": turn.role, "message": turn.message} for turn in reversed(prior_turns)
    ]

    return CompanionContext(
        student_name=student.full_name,
        recent_engagement_label=recent_engagement_label,
        recent_quiz_score=recent_quiz_score,
        current_difficulty_level=student.current_difficulty_level,
        student_message=student_message,
        conversation_history=conversation_history,
        detected_emotion=detected_emotion,
        sensory_sensitivity_score=(
            sensory_profile.sensory_sensitivity_score if sensory_profile else None
        ),
        interaction_mode=interaction_mode,
    )


def generate_companion_message(
    db: DBSession,
    student_id: int,
    student_message: str | None = None,
    interaction_mode: str = "chat",
) -> CompanionGenerationResult:
    """
    Generate a message from Mira for the given student, personalized
    from their existing data and prior conversation. Persists both the
    student's turn (with detected emotion) and Mira's reply to
    ConversationHistory, and logs the detected emotion to EmotionLog
    when a student_message was provided.

    Raises StudentNotFoundError if the student does not exist.
    """
    student = db.execute(select(Student).where(Student.id == student_id)).scalar_one_or_none()
    if student is None:
        raise StudentNotFoundError(f"Student {student_id} not found.")

    detected_emotion: str | None = None
    if student_message:
        prediction = classify_emotion(student_message)
        detected_emotion = prediction.emotion

        db.add(
            ConversationHistory(
                student_id=student.id,
                role="student",
                message=student_message,
                emotion_detected=detected_emotion,
            )
        )
        db.add(
            EmotionLog(
                student_id=student.id,
                emotion=detected_emotion,
                confidence=prediction.confidence,
                source="chat",
            )
        )

    context = _build_context(db, student, student_message, detected_emotion, interaction_mode)

    # The ONLY call into the provider layer - this service has no
    # knowledge of Gemini, Ollama, templates, or prompt construction.
    result = _ACTIVE_PROVIDER.generate_message(context)

    db.add(
        ConversationHistory(
            student_id=student.id,
            role="mira",
            message=result.message,
            emotion_detected=None,
        )
    )
    db.commit()

    return result


def get_conversation_history(db: DBSession, student_id: int, limit: int = 50) -> list[ConversationHistory]:
    """Return the most recent `limit` turns for a student, oldest-first."""
    rows = (
        db.execute(
            select(ConversationHistory)
            .where(ConversationHistory.student_id == student_id)
            .order_by(ConversationHistory.created_at.desc())
            .limit(limit)
        )
        .scalars()
        .all()
    )
    return list(reversed(rows))
