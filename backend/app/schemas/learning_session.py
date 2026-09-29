"""
schemas/learning_session.py

Pydantic request/response schemas for Learning Session assignment and
basic lifecycle tracking (Master Specification Section 5, 6, 10).

Field ownership (see Phase 7 planning verification for full reasoning):
    - student_id, learning_plan_id, learning_content_id: client-supplied
      on create — the teacher chooses these when assigning a session.
    - started_at, status, completed_at, difficulty_level_at_session:
      system-managed. difficulty_level_at_session in particular is a
      snapshot of the student's current difficulty at creation time
      (per the frozen model's docstring) and must never be client-set.
    - time_spent_seconds, idle_time_seconds, hint_usage_count,
      retry_count: the specification does not state who reports these.
      They are treated as optional values a caller may report when
      ending a session (complete/abandon), since they describe how the
      session went and are only meaningfully known once it has ended.

This phase implements only basic session assignment/lifecycle tracking.
No quiz, engagement prediction, or reflection fields are exposed here —
those belong to later phases.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class LearningSessionCreate(BaseModel):
    """Request body for POST /learning-sessions (teacher assigns a session)."""

    student_id: int
    learning_plan_id: int
    learning_content_id: int


class LearningSessionEndRequest(BaseModel):
    """
    Request body shared by the complete and abandon actions
    (POST /learning-sessions/{id}/complete and /abandon).

    All fields optional — a caller may report as much or as little of
    the session's engagement metrics as is known.
    """

    time_spent_seconds: int | None = Field(default=None, ge=0)
    idle_time_seconds: int | None = Field(default=None, ge=0)
    hint_usage_count: int | None = Field(default=None, ge=0)
    retry_count: int | None = Field(default=None, ge=0)


class LearningSessionResponse(BaseModel):
    """Response body for all learning session endpoints."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    student_id: int
    learning_plan_id: int
    learning_content_id: int
    started_at: datetime
    completed_at: datetime | None
    time_spent_seconds: int | None
    idle_time_seconds: int | None
    hint_usage_count: int
    retry_count: int
    status: str
    difficulty_level_at_session: str
