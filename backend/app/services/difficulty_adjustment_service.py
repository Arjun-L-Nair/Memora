"""
services/difficulty_adjustment_service.py

Business logic for Difficulty Adjustment (Master Specification Section
7: "The engagement prediction should influence: Lesson difficulty ...").

This module closes the neuroadaptive loop by deciding whether a
student's `current_difficulty_level` should move up, down, or stay the
same, based on an already-computed EngagementPrediction plus recent
quiz performance where available.

Design constraints (mirrors app/ai/adaptive_suggestion_rules.py
exactly, the frozen pattern already established for Adaptive
Suggestions):
    - PURE, self-contained rule engine. No ML/LLM. No import of
      sklearn, joblib, pandas, numpy, or any ML artifact. No
      dependency on app.ml whatsoever — this module only accepts
      already-computed prediction values as plain input, never calls
      predict_engagement() or touches a trained model.
    - Every function is pure: identical input always produces
      identical output. No randomness, no I/O, no database access.
    - Rules are stored as an ORDERED list of (name, predicate,
      builder) tuples — first match wins, exactly like
      adaptive_suggestion_rules.RULES.
    - Every decision names the rule that fired, satisfying "every
      recommendation should be explainable" (Section 7).

Difficulty levels are NOT redefined here. They are imported directly
from app.schemas.learning_content.DifficultyLevel — the single
existing source of truth for the "Beginner" / "Easy" / "Medium" /
"Hard" ordering (also used by Student.current_difficulty_level and
LearningContent.difficulty_level). This module never hardcodes a
second copy of that list.

This service does NOT write to the database and does NOT modify the
Student model. It is a pure decision function; wiring its output into
a persisted Student.current_difficulty_level update is a separate,
later step (explicitly out of scope for Module 1).
"""

from __future__ import annotations

from typing import Callable, NamedTuple

from pydantic import BaseModel

from app.schemas.learning_content import DifficultyLevel

__all__ = [
    "DIFFICULTY_ORDER",
    "DifficultyAdjustmentInput",
    "DifficultyAdjustmentResult",
    "decide_difficulty_adjustment",
]


# Canonical ordering of the existing DifficultyLevel values, lowest to
# highest. Reused (not duplicated in meaning) from
# app.schemas.learning_content.DifficultyLevel — this tuple exists only
# to give that same fixed set of literals a defined sequence, since
# Literal itself carries no ordering.
DIFFICULTY_ORDER: tuple[DifficultyLevel, ...] = ("Beginner", "Easy", "Medium", "Hard")


class DifficultyAdjustmentInput(BaseModel):
    """
    Plain input to the rule engine — already-computed values only.
    Never a database model, never something requiring a live model
    call to produce.

    Mirrors adaptive_suggestion_rules.SuggestionRuleInput's shape
    (engagement_label, engagement_score, quiz_accuracy) plus the one
    additional value this decision needs: the student's current
    difficulty level, so the engine knows which direction is even
    possible (e.g. it cannot move "Beginner" down further).
    """

    current_difficulty_level: DifficultyLevel
    engagement_label: str
    engagement_score: float
    quiz_accuracy: float | None = None
    hint_usage_count: int | None = None
    retry_count: int | None = None

    # --- Memora overhaul additions: multi-factor inputs ---
    # BKT-estimated mastery probability (0-1) for the skill just
    # practiced, from app.ml.learning_curve. None if not yet tracked.
    skill_mastery_probability: float | None = None
    # 0-1 sensory sensitivity score from SensoryProfile. High values
    # bias the engine toward NOT increasing difficulty even when
    # performance alone would suggest it, since a harder task usually
    # means more time pressure/cognitive load, which compounds poorly
    # with sensory overwhelm.
    sensory_sensitivity_score: float | None = None


class DifficultyAdjustmentResult(NamedTuple):
    """Output of a single rule: the new level, direction, and reasoning."""

    new_difficulty_level: DifficultyLevel
    direction: str  # "increase" | "decrease" | "maintain"
    reasoning: str


_Predicate = Callable[[DifficultyAdjustmentInput], bool]
_Builder = Callable[[DifficultyAdjustmentInput], DifficultyAdjustmentResult]


def _step(current: DifficultyLevel, delta: int) -> DifficultyLevel:
    """
    Move `delta` steps along DIFFICULTY_ORDER from `current`, clamped
    to the existing range (never produces a value outside the four
    known levels — "Beginner" is a floor, "Hard" is a ceiling).
    """
    index = DIFFICULTY_ORDER.index(current)
    new_index = max(0, min(len(DIFFICULTY_ORDER) - 1, index + delta))
    return DIFFICULTY_ORDER[new_index]


# --- Rule predicates/builders -----------------------------------------
#
# Thresholds intentionally mirror the ones already established in
# adaptive_suggestion_rules.py (accuracy < 0.5 as "struggling",
# hint_usage_count/retry_count <= 1 as "low effort/high mastery") so
# the two rule engines stay conceptually consistent rather than
# inventing a second, unrelated set of cutoffs.


def _rule_high_sensory_sensitivity_guard(x: DifficultyAdjustmentInput) -> bool:
    """
    Safety guard: for a highly sensory-sensitive student (score >=
    0.75), never increase difficulty this cycle even if performance
    signals would otherwise support it — added cognitive load from
    harder content compounds with sensory overwhelm. This rule only
    fires when it would actually change the outcome (i.e. some other
    rule would have increased difficulty); it does not override
    decreases or holds.
    """
    if x.sensory_sensitivity_score is None or x.sensory_sensitivity_score < 0.75:
        return False
    # Only intervene in the specific case that would otherwise increase.
    return x.engagement_label == "High" and (x.hint_usage_count or 0) <= 1 and (x.retry_count or 0) <= 1


def _build_high_sensory_sensitivity_guard(x: DifficultyAdjustmentInput) -> DifficultyAdjustmentResult:
    return DifficultyAdjustmentResult(
        new_difficulty_level=x.current_difficulty_level,
        direction="maintain",
        reasoning=(
            f"[Rule: SENSORY_OVERLOAD_GUARD] Performance signals would "
            f"otherwise support increasing difficulty, but this "
            f"student's sensory sensitivity score is "
            f"{x.sensory_sensitivity_score:.2f} (>= 0.75 threshold) — "
            f"difficulty is held at '{x.current_difficulty_level}' to "
            f"avoid compounding cognitive load with sensory overwhelm."
        ),
    )


def _rule_mastered_skill_increase(x: DifficultyAdjustmentInput) -> bool:
    return (
        x.skill_mastery_probability is not None
        and x.skill_mastery_probability >= 0.85
        and x.engagement_label != "Low"
    )


def _build_mastered_skill_increase(x: DifficultyAdjustmentInput) -> DifficultyAdjustmentResult:
    new_level = _step(x.current_difficulty_level, 1)
    direction = "increase" if new_level != x.current_difficulty_level else "maintain"
    return DifficultyAdjustmentResult(
        new_difficulty_level=new_level,
        direction=direction,
        reasoning=(
            f"[Rule: MASTERED_SKILL_INCREASE] BKT-estimated mastery "
            f"probability is {x.skill_mastery_probability:.2f} (>= 0.85 "
            f"threshold) and engagement was not 'Low' — the student has "
            f"demonstrated mastery of the current skill, so difficulty "
            f"is {'stepped up to ' + new_level if direction == 'increase' else 'held at the ceiling level'}."
        ),
    )


def _rule_low_engagement_low_accuracy(x: DifficultyAdjustmentInput) -> bool:
    return x.engagement_label == "Low" and x.quiz_accuracy is not None and x.quiz_accuracy < 0.5


def _build_low_engagement_low_accuracy(x: DifficultyAdjustmentInput) -> DifficultyAdjustmentResult:
    new_level = _step(x.current_difficulty_level, -1)
    direction = "decrease" if new_level != x.current_difficulty_level else "maintain"
    return DifficultyAdjustmentResult(
        new_difficulty_level=new_level,
        direction=direction,
        reasoning=(
            f"[Rule: LOW_ENGAGEMENT_LOW_ACCURACY] Engagement was 'Low' "
            f"(score={x.engagement_score:.2f}) and quiz accuracy was "
            f"{x.quiz_accuracy:.0%}, below the 50% threshold — the "
            f"student is struggling at the current level "
            f"('{x.current_difficulty_level}'), so difficulty is "
            f"{'stepped down to ' + new_level if direction == 'decrease' else 'held at the floor level'}."
        ),
    )


def _rule_low_engagement_ok_accuracy(x: DifficultyAdjustmentInput) -> bool:
    return x.engagement_label == "Low"


def _build_low_engagement_ok_accuracy(x: DifficultyAdjustmentInput) -> DifficultyAdjustmentResult:
    accuracy_note = (
        f"quiz accuracy was {x.quiz_accuracy:.0%}"
        if x.quiz_accuracy is not None
        else "no quiz was attempted"
    )
    return DifficultyAdjustmentResult(
        new_difficulty_level=x.current_difficulty_level,
        direction="maintain",
        reasoning=(
            f"[Rule: LOW_ENGAGEMENT_OK_ACCURACY] Engagement was 'Low' "
            f"(score={x.engagement_score:.2f}) even though {accuracy_note} "
            f"— since comprehension does not appear to be the cause, "
            f"difficulty is held at '{x.current_difficulty_level}' rather "
            f"than lowered; the underlying issue is more likely "
            f"attention/focus, not content difficulty."
        ),
    )


def _rule_medium_engagement(x: DifficultyAdjustmentInput) -> bool:
    return x.engagement_label == "Medium"


def _build_medium_engagement(x: DifficultyAdjustmentInput) -> DifficultyAdjustmentResult:
    return DifficultyAdjustmentResult(
        new_difficulty_level=x.current_difficulty_level,
        direction="maintain",
        reasoning=(
            f"[Rule: MEDIUM_ENGAGEMENT] Engagement was 'Medium' "
            f"(score={x.engagement_score:.2f}) — steady but not yet "
            f"strong, so difficulty is held at "
            f"'{x.current_difficulty_level}' until a clearer trend "
            f"emerges."
        ),
    )


def _rule_high_engagement_low_effort(x: DifficultyAdjustmentInput) -> bool:
    return (
        x.engagement_label == "High"
        and (x.hint_usage_count or 0) <= 1
        and (x.retry_count or 0) <= 1
    )


def _build_high_engagement_low_effort(x: DifficultyAdjustmentInput) -> DifficultyAdjustmentResult:
    new_level = _step(x.current_difficulty_level, 1)
    direction = "increase" if new_level != x.current_difficulty_level else "maintain"
    return DifficultyAdjustmentResult(
        new_difficulty_level=new_level,
        direction=direction,
        reasoning=(
            f"[Rule: HIGH_ENGAGEMENT_LOW_EFFORT] Engagement was 'High' "
            f"(score={x.engagement_score:.2f}) with hint_usage_count="
            f"{x.hint_usage_count or 0} and retry_count="
            f"{x.retry_count or 0}, both low — the current level "
            f"('{x.current_difficulty_level}') appears under-challenging, so "
            f"difficulty is "
            f"{'stepped up to ' + new_level if direction == 'increase' else 'held at the ceiling level'}."
        ),
    )


def _rule_high_engagement_default(x: DifficultyAdjustmentInput) -> bool:
    return x.engagement_label == "High"


def _build_high_engagement_default(x: DifficultyAdjustmentInput) -> DifficultyAdjustmentResult:
    return DifficultyAdjustmentResult(
        new_difficulty_level=x.current_difficulty_level,
        direction="maintain",
        reasoning=(
            f"[Rule: HIGH_ENGAGEMENT_DEFAULT] Engagement was 'High' "
            f"(score={x.engagement_score:.2f}) with meaningful hint/retry "
            f"usage — the current level ('{x.current_difficulty_level}') "
            f"appears well-matched, so difficulty is held steady."
        ),
    )


def _rule_fallback(_: DifficultyAdjustmentInput) -> bool:
    return True


def _build_fallback(x: DifficultyAdjustmentInput) -> DifficultyAdjustmentResult:
    return DifficultyAdjustmentResult(
        new_difficulty_level=x.current_difficulty_level,
        direction="maintain",
        reasoning=(
            f"[Rule: FALLBACK] engagement_label='{x.engagement_label}' did "
            f"not match any defined rule condition — difficulty is held "
            f"at '{x.current_difficulty_level}' as a safe default."
        ),
    )


# Ordered rule table — first match wins. Append new (name, predicate,
# builder) tuples here to add rules; nothing else needs to change.
RULES: list[tuple[str, _Predicate, _Builder]] = [
    ("SENSORY_OVERLOAD_GUARD", _rule_high_sensory_sensitivity_guard, _build_high_sensory_sensitivity_guard),
    ("LOW_ENGAGEMENT_LOW_ACCURACY", _rule_low_engagement_low_accuracy, _build_low_engagement_low_accuracy),
    ("LOW_ENGAGEMENT_OK_ACCURACY", _rule_low_engagement_ok_accuracy, _build_low_engagement_ok_accuracy),
    ("MEDIUM_ENGAGEMENT", _rule_medium_engagement, _build_medium_engagement),
    ("MASTERED_SKILL_INCREASE", _rule_mastered_skill_increase, _build_mastered_skill_increase),
    ("HIGH_ENGAGEMENT_LOW_EFFORT", _rule_high_engagement_low_effort, _build_high_engagement_low_effort),
    ("HIGH_ENGAGEMENT_DEFAULT", _rule_high_engagement_default, _build_high_engagement_default),
    ("FALLBACK", _rule_fallback, _build_fallback),
]


def decide_difficulty_adjustment(
    input_data: DifficultyAdjustmentInput,
) -> DifficultyAdjustmentResult:
    """
    Evaluate the ordered rule table against the given input and return
    the first matching rule's difficulty decision.

    Pure function: identical input always produces identical output.
    Never touches a database, a trained model, or any external service.
    Never mutates a Student row — the caller (a future integration
    step, out of scope for this module) is responsible for persisting
    `new_difficulty_level` if it chooses to.
    """
    for _name, predicate, builder in RULES:
        if predicate(input_data):
            return builder(input_data)

    # Unreachable in practice since _rule_fallback always matches, but
    # kept for exhaustiveness/type-safety.
    return _build_fallback(input_data)
