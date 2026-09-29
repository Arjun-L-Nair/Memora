"""
schemas/adaptive_suggestion.py

Pydantic response schema for Adaptive Suggestions (Master Specification
Section 6, 7: "Adaptive Suggestions", formerly "Teacher Recommendation
Engine").

Stateless/computed-on-demand (see Phase 10 planning, Assumption 2) — no
ORM model backs this schema, since nothing is persisted. No request
schema is needed either; the generating endpoint takes only a
learning_session_id path parameter, matching the
POST /engagement-predictions/{id}/generate pattern from Phase 9.
"""

from __future__ import annotations

from pydantic import BaseModel


class AdaptiveSuggestionResponse(BaseModel):
    """
    A single, rule-based, deterministic suggestion for a teacher,
    derived from one learning session's engagement prediction (and
    quiz performance, if available).

    reasoning is always populated — Section 7 requires every
    recommendation to be explainable, and the rule engine must not
    rely on an opaque model.
    """

    learning_session_id: int
    suggestion: str
    reasoning: str
    based_on_engagement_label: str
    based_on_engagement_score: float
