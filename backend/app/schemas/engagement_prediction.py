"""
schemas/engagement_prediction.py

Pydantic response schema for Engagement Predictions (Master
Specification Section 7, 10).

No request schema is needed for generating a prediction — the endpoint
(api/v1/ai.py) takes only a learning_session_id path parameter, no
body, matching the POST /quiz-attempts/start/{learning_session_id}
pattern from Phase 8.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class EngagementPredictionResponse(BaseModel):
    """Response body for all engagement prediction endpoints."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    learning_session_id: int
    quiz_accuracy: float | None
    time_spent_seconds: int | None
    idle_time_seconds: int | None
    hint_usage_count: int | None
    retry_count: int | None
    engagement_score: float
    engagement_label: str
    explanation: str | None
    predicted_at: datetime
