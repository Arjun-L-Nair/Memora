"""
services/admin_stats_service.py

Business logic for Admin-level system statistics (Master Specification
Section 4, 6, 16: Administrator, "Meaningful Analytics").

Mirrors analytics_service.py's func.count() aggregation style (Phase
12), but system-wide rather than per-student. No ownership check is
needed here — this data is inherently Admin-only; access control is
enforced at the router layer via get_current_admin (Module 6).

Deliberately minimal, per Phase 13 scope: basic counts only, no
time-series, no per-teacher/per-student breakdowns, no enterprise
reporting shape.
"""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import LearningSession, QuizAttempt, Student, Teacher
from app.schemas.admin import SystemStatisticsResponse


def get_system_statistics(db: Session) -> SystemStatisticsResponse:
    """
    Compute basic, system-wide platform statistics. Always succeeds;
    every count defaults to 0 on an empty database.
    """
    total_teachers = db.execute(select(func.count(Teacher.id))).scalar_one()
    active_teachers = db.execute(
        select(func.count(Teacher.id)).where(Teacher.is_active.is_(True))
    ).scalar_one()

    total_students = db.execute(select(func.count(Student.id))).scalar_one()
    active_students = db.execute(
        select(func.count(Student.id)).where(Student.is_active.is_(True))
    ).scalar_one()

    total_learning_sessions = db.execute(
        select(func.count(LearningSession.id))
    ).scalar_one()

    total_quiz_attempts = db.execute(
        select(func.count(QuizAttempt.id))
    ).scalar_one()

    return SystemStatisticsResponse(
        total_teachers=total_teachers,
        active_teachers=active_teachers,
        inactive_teachers=total_teachers - active_teachers,
        total_students=total_students,
        active_students=active_students,
        inactive_students=total_students - active_students,
        total_learning_sessions=total_learning_sessions,
        total_quiz_attempts=total_quiz_attempts,
    )
