"""
schemas/analytics.py

Pydantic response schema for the teacher-facing Analytics Dashboard
(Master Specification Section 6, 10, 16: Analytics Dashboard, Progress
Reports, "Meaningful Analytics").

Stateless/computed-on-demand, mirroring Adaptive Suggestions' design
(Phase 10) — no new database table. Aggregates existing LearningSession,
QuizAttempt, and EngagementPrediction data per Section 10's statement
that "session records are what feed the Analytics Dashboard."

The specification gives no concrete metric list, so this is a minimal,
explicit proposal: session counts by status, average quiz score, and
engagement label distribution — all tolerant of a student with no
sessions/quizzes/predictions yet (zero/None rather than an error).
"""

from __future__ import annotations

from pydantic import BaseModel


class StudentAnalyticsResponse(BaseModel):
    """Aggregated progress summary for a single student."""

    student_id: int
    total_sessions: int
    sessions_started: int
    sessions_completed: int
    sessions_abandoned: int
    total_quiz_attempts: int
    quizzes_submitted: int
    average_quiz_score: float | None
    total_engagement_predictions: int
    engagement_label_counts: dict[str, int]
