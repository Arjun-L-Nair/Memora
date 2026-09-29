"""
schemas/learning_reflection.py

Pydantic response schema for Learning Reflections (Master
Specification Section 6, 7, 10).

Mirrors the frozen LearningReflection ORM model's fields exactly. No
request schema is needed for generating a reflection — the endpoint
(api/v1/learning_reflection.py, Module 6) takes only a
learning_session_id path parameter, no body, matching the
POST /quiz-attempts/start/{id} and
POST /engagement-predictions/{id}/generate patterns from Phases 8/9.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class LearningReflectionResponse(BaseModel):
    """Response body for all learning reflection endpoints."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    learning_session_id: int
    content: str
    generated_by: str
    generated_at: datetime
