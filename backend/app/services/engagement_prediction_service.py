"""
services/engagement_prediction_service.py

Business logic for Engagement Predictions (Master Specification
Section 7, 10).

Reuses existing infrastructure rather than duplicating it:
    - Session ownership lookup: get_learning_session_for_teacher() and
      LearningSessionNotFoundError, reused directly from
      learning_session_service.py (frozen, Phase 7) — the exact same
      "session belongs to one of this teacher's own plans" check
      already used throughout Phases 6-8.
    - Prediction itself: calls ONLY app.ml.model.predict_engagement(),
      the public ML interface (Module 2). This service never imports
      DecisionTreeClassifier, joblib, or any other ML implementation
      detail directly — if the model changes later, only ml/model.py
      needs to change.

Lifecycle: exactly one EngagementPrediction per LearningSession
(enforced by the frozen unique=True constraint on
learning_session_id). Generating a second time for the same session
raises EngagementPredictionAlreadyExistsError, mirroring the
CREATED -> LOCKED pattern already used for QuizAttempt (Phase 8).

Phase 15 Module 2 — Difficulty Adjustment wiring:
    Once a new EngagementPrediction is built (but not yet committed),
    this service calls the frozen, pure, rule-based
    app.services.difficulty_adjustment_service.decide_difficulty_adjustment()
    with the student's current_difficulty_level plus the same
    engagement/quiz/behavior values already captured on the
    prediction. This introduces NO new ML/LLM call — the decision
    engine is deterministic and rule-based, exactly like Adaptive
    Suggestions (Phase 10).

    Student.current_difficulty_level is updated in the SAME
    transaction as the EngagementPrediction insert (one db.add() for
    each changed row, one db.commit() at the end) — never a second,
    separate commit. This preserves the existing transaction pattern
    (single commit per service call) and guarantees the prediction is
    never partially persisted: either both the prediction and any
    difficulty change land together, or neither does if the surrounding
    transaction fails. The student row is only added/touched when the
    decided level actually differs from the current one — "maintain"
    decisions never trigger a write.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session as DBSession

from app.ml.features import EngagementFeatures
from app.ml.model import predict_engagement
from app.models import (
    EngagementPrediction,
    LearningPlan,
    LearningSession,
    QuizAttempt,
    SensoryProfile,
    Student,
)
from app.services.difficulty_adjustment_service import (
    DifficultyAdjustmentInput,
    decide_difficulty_adjustment,
)
from app.services.learning_session_service import (
    LearningSessionNotFoundError,
    get_learning_session_for_teacher,
)

__all__ = [
    "LearningSessionNotFoundError",
    "EngagementPredictionAlreadyExistsError",
    "EngagementPredictionNotFoundError",
    "generate_engagement_prediction",
    "generate_engagement_prediction_for_session",
    "get_engagement_prediction_for_teacher",
]


class EngagementPredictionAlreadyExistsError(Exception):
    """Raised when attempting to generate a prediction for a session that already has one."""


class EngagementPredictionNotFoundError(Exception):
    """Raised when a prediction does not exist, or does not belong to the requesting teacher."""


def _extract_features(db: DBSession, session: LearningSession) -> EngagementFeatures:
    """
    Build the EngagementFeatures for a session: the 5 persisted
    session-level indicators (unchanged), plus extended
    temporal/historical/sensory context derived from real data where
    available — this is what actually populates the 18-feature model
    input beyond the frozen persisted snapshot. Every extended field
    degrades gracefully to None (-> neutral default in
    ml/features.to_model_input) when the underlying data doesn't exist
    yet (e.g. a brand-new student with no session history).
    """
    quiz_attempt = db.execute(
        select(QuizAttempt).where(QuizAttempt.learning_session_id == session.id)
    ).scalar_one_or_none()

    # Prior sessions for this student, most recent first, excluding
    # this one — used for temporal/historical features.
    prior_sessions = (
        db.execute(
            select(LearningSession)
            .where(
                LearningSession.student_id == session.student_id,
                LearningSession.id != session.id,
                LearningSession.created_at < session.created_at,
            )
            .order_by(LearningSession.created_at.desc())
            .limit(10)
        )
        .scalars()
        .all()
    )

    now = session.created_at or datetime.utcnow()

    days_since_last_session: float | None = None
    sessions_this_week = 0
    if prior_sessions:
        days_since_last_session = (now - prior_sessions[0].created_at).total_seconds() / 86400.0
        sessions_this_week = sum(
            1 for s in prior_sessions if (now - s.created_at).days <= 7
        )

    # Rolling average accuracy over the last 5 prior sessions with a
    # recorded QuizAttempt (skips sessions with none, rather than
    # treating a missing quiz as 0% accuracy).
    recent_accuracies: list[float] = []
    for prior in prior_sessions[:5]:
        prior_quiz = db.execute(
            select(QuizAttempt).where(QuizAttempt.learning_session_id == prior.id)
        ).scalar_one_or_none()
        if prior_quiz is not None:
            recent_accuracies.append(prior_quiz.accuracy)
    rolling_avg_accuracy_5 = (
        sum(recent_accuracies) / len(recent_accuracies) if recent_accuracies else None
    )

    # Simple engagement trend slope: difference between the most
    # recent prior prediction's score and the one before it, if both
    # exist. A cheap proxy rather than a full linear regression, since
    # 2 points is all early sessions can offer anyway.
    engagement_trend_slope: float | None = None
    recent_predictions = [
        db.execute(
            select(EngagementPrediction).where(EngagementPrediction.learning_session_id == s.id)
        ).scalar_one_or_none()
        for s in prior_sessions[:2]
    ]
    recent_predictions = [p for p in recent_predictions if p is not None]
    if len(recent_predictions) == 2:
        engagement_trend_slope = recent_predictions[0].engagement_score - recent_predictions[1].engagement_score

    sensory_profile = db.execute(
        select(SensoryProfile).where(SensoryProfile.student_id == session.student_id)
    ).scalar_one_or_none()

    return EngagementFeatures(
        quiz_accuracy=quiz_attempt.accuracy if quiz_attempt is not None else None,
        time_spent_seconds=session.time_spent_seconds,
        idle_time_seconds=session.idle_time_seconds,
        hint_usage_count=session.hint_usage_count,
        retry_count=session.retry_count,
        session_hour_of_day=now.hour,
        day_of_week=now.weekday(),
        sessions_this_week=sessions_this_week,
        days_since_last_session=days_since_last_session,
        rolling_avg_accuracy_5=rolling_avg_accuracy_5,
        engagement_trend_slope=engagement_trend_slope,
        preferred_mode=sensory_profile.preferred_mode if sensory_profile else None,
        sensory_sensitivity_score=sensory_profile.sensory_sensitivity_score if sensory_profile else None,
        attention_span_minutes=sensory_profile.attention_span_minutes if sensory_profile else None,
    )


def generate_engagement_prediction(
    db: DBSession, teacher_id: int, learning_session_id: int
) -> EngagementPrediction:
    """
    Generate and persist a new engagement prediction for one of the
    teacher's own learning sessions. Teacher-facing entry point — verifies
    ownership, then delegates to _generate_engagement_prediction_core().

    Raises:
        LearningSessionNotFoundError: session doesn't exist or isn't
            owned by this teacher.
        EngagementPredictionAlreadyExistsError: a prediction already
            exists for this session.
    """
    session = get_learning_session_for_teacher(db, teacher_id, learning_session_id)
    return _generate_engagement_prediction_core(db, session)


def generate_engagement_prediction_for_session(
    db: DBSession, session: LearningSession
) -> EngagementPrediction:
    """
    Generate and persist an engagement prediction for an
    already-fetched, already-ownership-verified LearningSession.

    This is the entry point used by the STUDENT-facing completion flow
    (student_learning_service.complete_session_as_student) — called
    automatically the moment a student finishes a session, so a
    prediction exists without any separate teacher action. The teacher
    -facing generate_engagement_prediction() above is now a thin
    ownership-check wrapper around the same core logic, so both paths
    produce identical predictions.

    Raises EngagementPredictionAlreadyExistsError if one already
    exists for this session (idempotent-safe to call defensively).
    """
    return _generate_engagement_prediction_core(db, session)


def _generate_engagement_prediction_core(
    db: DBSession, session: LearningSession
) -> EngagementPrediction:
    """Shared implementation — see the two public entry points above for the ownership-check contract each provides."""
    existing = db.execute(
        select(EngagementPrediction).where(
            EngagementPrediction.learning_session_id == session.id
        )
    ).scalar_one_or_none()
    if existing is not None:
        raise EngagementPredictionAlreadyExistsError(
            f"An engagement prediction already exists for session {session.id}."
        )

    features = _extract_features(db, session)

    # The ONLY ML call in this service — everything about how the
    # prediction is produced is hidden behind this one function.
    result = predict_engagement(features)

    prediction = EngagementPrediction(
        learning_session_id=session.id,
        quiz_accuracy=features.quiz_accuracy,
        time_spent_seconds=features.time_spent_seconds,
        idle_time_seconds=features.idle_time_seconds,
        hint_usage_count=features.hint_usage_count,
        retry_count=features.retry_count,
        engagement_score=result.engagement_score,
        engagement_label=result.engagement_label,
        explanation=result.explanation,
    )
    db.add(prediction)

    # --- Phase 15 Module 2: difficulty adjustment -------------------
    #
    # Student existence/ownership is already implied by the session
    # ownership check the caller performed before reaching here — only
    # the row itself is needed now, to read and possibly update
    # current_difficulty_level.
    student = db.get(Student, session.student_id)
    assert student is not None  # guaranteed by the session's FK

    adjustment_input = DifficultyAdjustmentInput(
        current_difficulty_level=student.current_difficulty_level,
        engagement_label=result.engagement_label,
        engagement_score=result.engagement_score,
        quiz_accuracy=features.quiz_accuracy,
        hint_usage_count=features.hint_usage_count,
        retry_count=features.retry_count,
        sensory_sensitivity_score=features.sensory_sensitivity_score,
    )
    # The ONLY call into the difficulty rule engine — deterministic,
    # rule-based, no ML/LLM involved. Never touches the database or
    # the trained engagement model.
    adjustment = decide_difficulty_adjustment(adjustment_input)

    # Persist the new level only when it actually differs — "maintain"
    # decisions never touch the student row.
    if adjustment.new_difficulty_level != student.current_difficulty_level:
        student.current_difficulty_level = adjustment.new_difficulty_level
        db.add(student)

    # Single commit for both rows: the prediction and (if applicable)
    # the student's updated difficulty level are persisted together,
    # in the same transaction. If the commit fails, nothing here is
    # left partially applied.
    db.commit()
    db.refresh(prediction)
    return prediction


def get_engagement_prediction_for_teacher(
    db: DBSession, teacher_id: int, prediction_id: int
) -> EngagementPrediction:
    """
    Get a single engagement prediction by id, scoped to the requesting
    teacher via its session's plan ownership.
    """
    prediction = db.execute(
        select(EngagementPrediction)
        .join(LearningSession)
        .join(LearningPlan)
        .where(
            EngagementPrediction.id == prediction_id,
            LearningPlan.teacher_id == teacher_id,
        )
    ).scalar_one_or_none()

    if prediction is None:
        raise EngagementPredictionNotFoundError(
            f"Engagement prediction {prediction_id} not found."
        )

    return prediction
