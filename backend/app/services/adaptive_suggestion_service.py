"""
services/adaptive_suggestion_service.py

Business logic for Adaptive Suggestions (Master Specification Section
6, 7).

This service is intentionally thin and rule-agnostic:
    1. Verify ownership (reused from Phase 7/9 — never duplicated).
    2. Load the session's already-persisted EngagementPrediction
       (Phase 9) as the single data source — its snapshot columns
       (quiz_accuracy, hint_usage_count, retry_count) already capture
       everything the rule engine needs, so no separate QuizAttempt
       query is required here.
    3. Call app.ai.adaptive_suggestion_rules.generate_suggestion()
       EXACTLY ONCE.
    4. Return the response.

This module has NO knowledge of individual rules, rule names, or rule
conditions — that logic lives entirely in
app.ai.adaptive_suggestion_rules, the single source of truth. This
module also never imports app.ml or anything ML-related; Adaptive
Suggestions consumes an already-computed EngagementPrediction row, it
never calls predict_engagement() or touches a trained model.

Stateless: nothing is persisted here (see Phase 10 planning,
Assumption 2) — a suggestion is computed fresh on every request.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session as DBSession

from app.ai.adaptive_suggestion_rules import SuggestionRuleInput, generate_suggestion
from app.models import EngagementPrediction
from app.schemas.adaptive_suggestion import AdaptiveSuggestionResponse
from app.services.engagement_prediction_service import (
    EngagementPredictionNotFoundError,
    LearningSessionNotFoundError,
)
from app.services.learning_session_service import get_learning_session_for_teacher

__all__ = [
    "LearningSessionNotFoundError",
    "EngagementPredictionNotFoundError",
    "get_adaptive_suggestion",
]


def get_adaptive_suggestion(
    db: DBSession, teacher_id: int, learning_session_id: int
) -> AdaptiveSuggestionResponse:
    """
    Compute an Adaptive Suggestion for one of the teacher's own
    learning sessions, based on its already-generated
    EngagementPrediction.

    Raises:
        LearningSessionNotFoundError: session doesn't exist or isn't
            owned by this teacher.
        EngagementPredictionNotFoundError: no EngagementPrediction has
            been generated for this session yet (see Phase 9,
            POST /engagement-predictions/{id}/generate).
    """
    # Ownership check reused directly from Phase 7 — never duplicated.
    get_learning_session_for_teacher(db, teacher_id, learning_session_id)

    prediction = db.execute(
        select(EngagementPrediction).where(
            EngagementPrediction.learning_session_id == learning_session_id
        )
    ).scalar_one_or_none()

    if prediction is None:
        raise EngagementPredictionNotFoundError(
            f"No engagement prediction exists yet for session "
            f"{learning_session_id}. Generate one first."
        )

    rule_input = SuggestionRuleInput(
        engagement_label=prediction.engagement_label,
        engagement_score=prediction.engagement_score,
        quiz_accuracy=prediction.quiz_accuracy,
        hint_usage_count=prediction.hint_usage_count,
        retry_count=prediction.retry_count,
    )

    # The ONLY call into the rule engine — the service has no
    # knowledge of which rule fires or why.
    result = generate_suggestion(rule_input)

    return AdaptiveSuggestionResponse(
        learning_session_id=learning_session_id,
        suggestion=result.suggestion,
        reasoning=result.reasoning,
        based_on_engagement_label=prediction.engagement_label,
        based_on_engagement_score=prediction.engagement_score,
    )
