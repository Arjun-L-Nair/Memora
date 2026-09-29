"""
schemas/student_learning.py

Schemas for the student-facing learning workflow (Master Specification
Section 5, 6: Today's Learning, Progress Tracking).

No new session response shape is defined here — a student's view of
their own session is structurally identical to a teacher's view
(schemas/learning_session.py's LearningSessionResponse, frozen Phase 7),
so it is reused directly rather than duplicated.

Phase 15 Module 4 — Adaptive Content Recommendation (student-facing):
    RecommendedContentResponse wraps the plan id, the recommended
    content (or null — a graceful, expected outcome when no active
    content exists), and a short explanation of why it was picked.
    The `content` field reuses LearningContentResponse directly
    (schemas/learning_content.py, frozen) rather than defining a
    second, parallel content shape.
"""

from __future__ import annotations

from pydantic import BaseModel

from app.schemas.learning_content import LearningContentResponse
from app.schemas.learning_session import LearningSessionResponse

__all__ = ["LearningSessionResponse", "RecommendedContentResponse"]


class RecommendedContentResponse(BaseModel):
    """
    Response body for GET /student-learning/plans/{learning_plan_id}/recommended-content.

    `content` is None when the plan has no active learning content to
    recommend — this is represented explicitly rather than as an error,
    so the student-facing UI can show a calm "nothing available yet"
    state instead of an error screen.
    """

    learning_plan_id: int
    content: LearningContentResponse | None
    reasoning: str
