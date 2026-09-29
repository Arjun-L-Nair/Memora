"""
services/analytics_service.py

Business logic for the teacher-facing Analytics Dashboard (Master
Specification Section 6, 10, 16).

Reuses get_student_for_teacher() and StudentNotFoundError directly from
student_service.py (frozen, Phase 5) for ownership — never duplicated.

Stateless: every value here is computed fresh from existing
LearningSession, QuizAttempt, and EngagementPrediction rows on each
request; nothing is persisted (mirrors Adaptive Suggestions, Phase 10).
"""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session as DBSession

from app.models import EngagementPrediction, LearningSession, QuizAttempt
from app.schemas.analytics import StudentAnalyticsResponse
from app.services.student_service import StudentNotFoundError, get_student_for_teacher

__all__ = ["StudentNotFoundError", "get_student_analytics"]


def get_student_analytics(
    db: DBSession, teacher_id: int, student_id: int
) -> StudentAnalyticsResponse:
    """
    Compute an aggregated progress summary for one of the teacher's own
    students.

    Raises StudentNotFoundError if the student does not exist or is not
    owned by this teacher.
    """
    # Ownership check reused directly from Phase 5 — never duplicated.
    get_student_for_teacher(db, teacher_id, student_id)

    # --- Session counts by status ---
    status_rows = db.execute(
        select(LearningSession.status, func.count(LearningSession.id))
        .where(LearningSession.student_id == student_id)
        .group_by(LearningSession.status)
    ).all()
    status_counts = {status: count for status, count in status_rows}
    total_sessions = sum(status_counts.values())

    # --- Quiz attempt stats ---
    quiz_rows = db.execute(
        select(QuizAttempt.score)
        .join(LearningSession, QuizAttempt.learning_session_id == LearningSession.id)
        .where(LearningSession.student_id == student_id)
    ).all()
    quiz_scores = [row[0] for row in quiz_rows]
    submitted_scores = [s for s in quiz_scores if s is not None]
    average_quiz_score = (
        sum(submitted_scores) / len(submitted_scores) if submitted_scores else None
    )

    # --- Engagement prediction label distribution ---
    engagement_rows = db.execute(
        select(EngagementPrediction.engagement_label, func.count(EngagementPrediction.id))
        .join(LearningSession, EngagementPrediction.learning_session_id == LearningSession.id)
        .where(LearningSession.student_id == student_id)
        .group_by(EngagementPrediction.engagement_label)
    ).all()
    engagement_label_counts = {label: count for label, count in engagement_rows}
    total_predictions = sum(engagement_label_counts.values())

    return StudentAnalyticsResponse(
        student_id=student_id,
        total_sessions=total_sessions,
        sessions_started=status_counts.get("started", 0),
        sessions_completed=status_counts.get("completed", 0),
        sessions_abandoned=status_counts.get("abandoned", 0),
        total_quiz_attempts=len(quiz_scores),
        quizzes_submitted=len(submitted_scores),
        average_quiz_score=average_quiz_score,
        total_engagement_predictions=total_predictions,
        engagement_label_counts=engagement_label_counts,
    )
