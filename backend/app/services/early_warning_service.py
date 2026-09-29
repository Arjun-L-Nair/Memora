"""
services/early_warning_service.py

Business logic for the Early-Warning / dropout-risk dashboard
(Memora overhaul, Component 4).

Reuses get_student_for_teacher()/StudentNotFoundError directly from
student_service.py, same ownership-check pattern as analytics_service.py.
Builds a SessionSignal list from the student's own LearningSession +
EngagementPrediction + QuizAttempt history and delegates the actual
scoring to the pure, rule-based app.ml.early_warning.compute_risk_score().

Also persists the latest risk_score onto LearningPattern (one row per
student, upserted) so the score is queryable without recomputation for
list-view dashboards (get_at_risk_students_for_teacher below).
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session as DBSession

from app.ml.early_warning import EarlyWarningResult, SessionSignal, compute_risk_score
from app.models import EngagementPrediction, LearningPattern, LearningSession, QuizAttempt, Student
from app.services.student_service import StudentNotFoundError, get_student_for_teacher

__all__ = [
    "StudentNotFoundError",
    "get_early_warning_for_student",
    "get_at_risk_students_for_teacher",
]


def _build_session_signals(db: DBSession, student_id: int, limit: int = 30) -> list[SessionSignal]:
    sessions = (
        db.execute(
            select(LearningSession)
            .where(LearningSession.student_id == student_id)
            .order_by(LearningSession.created_at.desc())
            .limit(limit)
        )
        .scalars()
        .all()
    )

    signals: list[SessionSignal] = []
    for session in sessions:
        prediction = db.execute(
            select(EngagementPrediction).where(EngagementPrediction.learning_session_id == session.id)
        ).scalar_one_or_none()
        quiz_attempt = db.execute(
            select(QuizAttempt).where(QuizAttempt.learning_session_id == session.id)
        ).scalar_one_or_none()

        signals.append(
            SessionSignal(
                created_at=session.created_at,
                engagement_score=prediction.engagement_score if prediction else None,
                quiz_accuracy=quiz_attempt.accuracy if quiz_attempt else None,
            )
        )
    return signals


def _upsert_learning_pattern_risk(db: DBSession, student_id: int, risk_score: float) -> None:
    pattern = db.execute(
        select(LearningPattern).where(LearningPattern.student_id == student_id)
    ).scalar_one_or_none()
    if pattern is None:
        pattern = LearningPattern(student_id=student_id, risk_score=risk_score)
        db.add(pattern)
    else:
        pattern.risk_score = risk_score
        db.add(pattern)
    db.commit()


def get_early_warning_for_student(db: DBSession, teacher_id: int, student_id: int) -> EarlyWarningResult:
    """
    Compute (and persist) the current dropout-risk score for one of the
    teacher's own students.

    Raises StudentNotFoundError if the student doesn't exist or isn't
    owned by this teacher.
    """
    get_student_for_teacher(db, teacher_id, student_id)  # ownership check only

    signals = _build_session_signals(db, student_id)
    result = compute_risk_score(signals)
    _upsert_learning_pattern_risk(db, student_id, result.risk_score)
    return result


def get_at_risk_students_for_teacher(
    db: DBSession, teacher_id: int, risk_threshold: float = 50.0
) -> list[dict]:
    """
    Compute risk scores for every student belonging to this teacher
    (via their LearningPlans) and return those at or above
    risk_threshold, sorted highest-risk first. Used for the Early
    Warning dashboard list view.

    Note: this recomputes for every student on each call rather than
    reading only the persisted LearningPattern.risk_score, so the list
    is always fresh even if a student hasn't been individually viewed
    recently. For a large student roster this could be optimized to a
    background/scheduled job later; not necessary at current scale.
    """
    # Queries Student.teacher_id directly — Student already has this
    # FK, so going through LearningPlan (as this used to) was an
    # unnecessary indirection, and one that broke under the plan-reuse
    # restructure anyway (a plan's student_id is no longer reliably
    # "this plan's student"; a plan can now be assigned to many
    # students, or none, via PlanAssignment instead).
    student_ids = (
        db.execute(
            select(Student.id).where(Student.teacher_id == teacher_id)
        )
        .scalars()
        .all()
    )

    results = []
    for student_id in student_ids:
        signals = _build_session_signals(db, student_id)
        result = compute_risk_score(signals)
        _upsert_learning_pattern_risk(db, student_id, result.risk_score)
        if result.risk_score >= risk_threshold:
            student = db.get(Student, student_id)
            results.append(
                {
                    "student_id": student_id,
                    "student_name": student.full_name if student else "Unknown",
                    "risk_score": result.risk_score,
                    "risk_level": result.risk_level,
                    "contributing_factors": result.contributing_factors,
                }
            )

    results.sort(key=lambda r: r["risk_score"], reverse=True)
    return results
