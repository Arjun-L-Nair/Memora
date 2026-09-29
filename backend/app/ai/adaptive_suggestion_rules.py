"""
ai/adaptive_suggestion_rules.py

Adaptive Suggestions rule engine (Master Specification Section 6, 7).

Per Section 7's explicit requirement — "Adaptive Suggestions must be:
Simple, Rule-based, Deterministic... must not rely on opaque or
non-explainable models" — this module is a PURE, self-contained rule
engine:
    - No import of sklearn, joblib, pandas, numpy, or any ML artifact.
    - No dependency on app.ml (the Engagement Prediction ML package)
      whatsoever, even indirectly — this module only accepts already-
      computed prediction values as plain input, never calls
      predict_engagement() or touches any trained model.
    - Every function here is pure: identical input always produces
      identical output. No randomness, no I/O, no database access.

Rules are stored as an ORDERED list of (name, predicate, builder)
tuples in RULES below — the first matching rule wins. Adding a new
rule means appending one tuple to that list; nothing else in this
file, the service layer, or the router needs to change.

Each produced suggestion's reasoning explicitly names which rule fired
(via its `name`), satisfying "every recommendation should be
explainable."
"""

from __future__ import annotations

from typing import Callable, NamedTuple

from pydantic import BaseModel


class SuggestionRuleInput(BaseModel):
    """
    Plain input to the rule engine — already-computed values only.
    Never a database model, never something requiring a live model
    call to produce.
    """

    engagement_label: str
    engagement_score: float
    quiz_accuracy: float | None = None
    hint_usage_count: int | None = None
    retry_count: int | None = None


class SuggestionResult(NamedTuple):
    """Output of a single rule: the suggestion text and its explanation."""

    suggestion: str
    reasoning: str


_Predicate = Callable[[SuggestionRuleInput], bool]
_Builder = Callable[[SuggestionRuleInput], SuggestionResult]


def _rule_low_engagement_low_accuracy(x: SuggestionRuleInput) -> bool:
    return x.engagement_label == "Low" and x.quiz_accuracy is not None and x.quiz_accuracy < 0.5


def _build_low_engagement_low_accuracy(x: SuggestionRuleInput) -> SuggestionResult:
    return SuggestionResult(
        suggestion=(
            "Schedule a one-on-one review of this lesson's core concepts "
            "before the student moves forward."
        ),
        reasoning=(
            f"[Rule: LOW_ENGAGEMENT_LOW_ACCURACY] Engagement was 'Low' "
            f"(score={x.engagement_score:.2f}) and quiz accuracy was "
            f"{x.quiz_accuracy:.0%}, below the 50% threshold — indicating "
            f"the student struggled with both focus and comprehension."
        ),
    )


def _rule_low_engagement_ok_accuracy(x: SuggestionRuleInput) -> bool:
    return x.engagement_label == "Low"


def _build_low_engagement_ok_accuracy(x: SuggestionRuleInput) -> SuggestionResult:
    accuracy_note = (
        f"quiz accuracy was {x.quiz_accuracy:.0%}"
        if x.quiz_accuracy is not None
        else "no quiz was attempted"
    )
    return SuggestionResult(
        suggestion=(
            "Check in with the student directly; low engagement was not "
            "reflected in quiz performance, which may indicate "
            "distraction or disengagement unrelated to content difficulty."
        ),
        reasoning=(
            f"[Rule: LOW_ENGAGEMENT_OK_ACCURACY] Engagement was 'Low' "
            f"(score={x.engagement_score:.2f}) even though {accuracy_note} "
            f"— the low engagement does not appear to be explained by "
            f"comprehension difficulty alone."
        ),
    )


def _rule_medium_engagement(x: SuggestionRuleInput) -> bool:
    return x.engagement_label == "Medium"


def _build_medium_engagement(x: SuggestionRuleInput) -> SuggestionResult:
    return SuggestionResult(
        suggestion=(
            "Monitor the student's next session and consider light "
            "reinforcement activities to build consistency."
        ),
        reasoning=(
            f"[Rule: MEDIUM_ENGAGEMENT] Engagement was 'Medium' "
            f"(score={x.engagement_score:.2f}) — steady but not yet "
            f"strong, so continued observation is warranted before "
            f"changing course."
        ),
    )


def _rule_high_engagement_low_effort(x: SuggestionRuleInput) -> bool:
    return (
        x.engagement_label == "High"
        and (x.hint_usage_count or 0) <= 1
        and (x.retry_count or 0) <= 1
    )


def _build_high_engagement_low_effort(x: SuggestionRuleInput) -> SuggestionResult:
    return SuggestionResult(
        suggestion=(
            "Consider introducing more challenging content — the student "
            "is engaging strongly with minimal need for hints or retries."
        ),
        reasoning=(
            f"[Rule: HIGH_ENGAGEMENT_LOW_EFFORT] Engagement was 'High' "
            f"(score={x.engagement_score:.2f}) with hint_usage_count="
            f"{x.hint_usage_count or 0} and retry_count={x.retry_count or 0}, "
            f"both low — suggesting the current difficulty level may be "
            f"under-challenging the student."
        ),
    )


def _rule_high_engagement_default(x: SuggestionRuleInput) -> bool:
    return x.engagement_label == "High"


def _build_high_engagement_default(x: SuggestionRuleInput) -> SuggestionResult:
    return SuggestionResult(
        suggestion="Continue with the current lesson pace and structure.",
        reasoning=(
            f"[Rule: HIGH_ENGAGEMENT_DEFAULT] Engagement was 'High' "
            f"(score={x.engagement_score:.2f}) — the current approach "
            f"appears to be working well for this student."
        ),
    )


def _rule_fallback(_: SuggestionRuleInput) -> bool:
    return True


def _build_fallback(x: SuggestionRuleInput) -> SuggestionResult:
    return SuggestionResult(
        suggestion="Review this session's data manually; no specific rule matched.",
        reasoning=(
            f"[Rule: FALLBACK] engagement_label='{x.engagement_label}' did "
            f"not match any defined rule condition."
        ),
    )


# Ordered rule table — first match wins. Append new (name, predicate,
# builder) tuples here to add rules; nothing else needs to change.
RULES: list[tuple[str, _Predicate, _Builder]] = [
    ("LOW_ENGAGEMENT_LOW_ACCURACY", _rule_low_engagement_low_accuracy, _build_low_engagement_low_accuracy),
    ("LOW_ENGAGEMENT_OK_ACCURACY", _rule_low_engagement_ok_accuracy, _build_low_engagement_ok_accuracy),
    ("MEDIUM_ENGAGEMENT", _rule_medium_engagement, _build_medium_engagement),
    ("HIGH_ENGAGEMENT_LOW_EFFORT", _rule_high_engagement_low_effort, _build_high_engagement_low_effort),
    ("HIGH_ENGAGEMENT_DEFAULT", _rule_high_engagement_default, _build_high_engagement_default),
    ("FALLBACK", _rule_fallback, _build_fallback),
]


def generate_suggestion(input_data: SuggestionRuleInput) -> SuggestionResult:
    """
    Evaluate the ordered rule table against the given input and return
    the first matching rule's suggestion + reasoning.

    Pure function: identical input always produces identical output.
    Never touches a database, a trained model, or any external service.
    """
    for _name, predicate, builder in RULES:
        if predicate(input_data):
            return builder(input_data)

    # Unreachable in practice since _rule_fallback always matches, but
    # kept for exhaustiveness/type-safety.
    return _build_fallback(input_data)
