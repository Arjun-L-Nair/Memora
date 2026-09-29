"""
ml/learning_curve.py

Bayesian Knowledge Tracing (BKT) for per-skill mastery estimation, plus
an SM-2-derived spaced repetition scheduler adapted for ASD learners
(longer intervals, more repetition passes before an item is considered
"learned"). Part of the Memora ML overhaul, Component 1 / 5.

BKT background:
    Classic 4-parameter BKT (Corbett & Anderson, 1994) models mastery
    of a single skill as a hidden binary state (known / not known)
    updated after each observed attempt (correct / incorrect) via
    Bayes' rule, using four parameters:
        p_init  - prior probability the skill is already known
        p_transit - probability of learning it on any given attempt
        p_slip  - probability of a wrong answer despite knowing it
        p_guess - probability of a right answer despite not knowing it
    This module keeps those parameters as fixed, documented defaults
    (tunable per content area later) rather than fitting them via EM,
    which needs more historical data than a fresh deployment has.

Spaced repetition:
    A simplified SM-2 (SuperMemo-2) variant. ASD-specific adaptation
    per the plan: intervals grow more slowly (a gentler ease factor
    floor) and more repetitions are required before an item exits the
    "learning" queue, since over-generalizing after one success is a
    documented poor fit for some autistic learners' need for
    predictability and repeated exposure.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from pydantic import BaseModel

# --- BKT default parameters (fixed, documented, not fit via EM) ---
_DEFAULT_P_INIT = 0.3
_DEFAULT_P_TRANSIT = 0.15
_DEFAULT_P_SLIP = 0.10
_DEFAULT_P_GUESS = 0.20

# Mastery threshold: a skill is considered "mastered" once P(known) >= this.
MASTERY_THRESHOLD = 0.85


class SkillMasteryState(BaseModel):
    """Current BKT belief state for one student-skill pair."""

    p_known: float
    attempts: int
    is_mastered: bool


def initial_mastery_state(p_init: float = _DEFAULT_P_INIT) -> SkillMasteryState:
    """Starting belief before any attempts are observed."""
    return SkillMasteryState(p_known=p_init, attempts=0, is_mastered=p_init >= MASTERY_THRESHOLD)


def update_mastery(
    state: SkillMasteryState,
    correct: bool,
    p_transit: float = _DEFAULT_P_TRANSIT,
    p_slip: float = _DEFAULT_P_SLIP,
    p_guess: float = _DEFAULT_P_GUESS,
) -> SkillMasteryState:
    """
    Bayesian update of P(known) given one new observed attempt.

    Step 1 (evidence update, Bayes' rule):
        if correct:
            P(known | correct) = P(known) * (1 - p_slip)
                                 / [P(known)*(1-p_slip) + (1-P(known))*p_guess]
        if incorrect:
            P(known | incorrect) = P(known) * p_slip
                                   / [P(known)*p_slip + (1-P(known))*(1-p_guess)]

    Step 2 (learning transition — even if not known before this
    attempt, the student may have learned it during/because of it):
        P(known)_next = P(known | evidence) + (1 - P(known | evidence)) * p_transit
    """
    p_known = state.p_known

    if correct:
        numerator = p_known * (1 - p_slip)
        denominator = numerator + (1 - p_known) * p_guess
    else:
        numerator = p_known * p_slip
        denominator = numerator + (1 - p_known) * (1 - p_guess)

    p_known_given_evidence = numerator / denominator if denominator > 0 else p_known
    p_known_next = p_known_given_evidence + (1 - p_known_given_evidence) * p_transit

    return SkillMasteryState(
        p_known=p_known_next,
        attempts=state.attempts + 1,
        is_mastered=p_known_next >= MASTERY_THRESHOLD,
    )


# --- Spaced repetition (SM-2, ASD-adapted) ---

# ASD adaptation: floor the ease factor higher than vanilla SM-2's 1.3,
# so intervals shrink less aggressively after a lapse, and require a
# 4th consecutive correct repetition (vs. SM-2's usual 3) before an
# item is treated as "learned" and moved to long-interval review.
_MIN_EASE_FACTOR = 1.6
_REPETITIONS_TO_LEARNED = 4


@dataclass
class SpacedRepetitionCard:
    """Scheduling state for one (student, content_item) pair."""

    ease_factor: float = 2.3  # slightly below vanilla SM-2's 2.5 default: gentler ramp
    interval_days: int = 1
    repetitions: int = 0
    due_at: datetime | None = None

    def review(self, quality: int, now: datetime | None = None) -> "SpacedRepetitionCard":
        """
        Apply one review outcome. `quality` is 0-5 (SM-2 scale: 0 =
        total blackout, 5 = perfect recall). Returns a new card state
        (does not mutate in place, so callers can persist the result
        explicitly rather than relying on side effects).
        """
        now = now or datetime.utcnow()

        if quality < 3:
            # Lapse: reset repetitions, but the ASD-adapted ease floor
            # keeps the next interval gentler than a from-scratch item.
            repetitions = 0
            interval_days = 1
        else:
            repetitions = self.repetitions + 1
            if repetitions == 1:
                interval_days = 1
            elif repetitions == 2:
                interval_days = 6
            else:
                interval_days = round(self.interval_days * self.ease_factor)

        ease_factor = self.ease_factor + (0.1 - (5 - quality) * (0.08 + (5 - quality) * 0.02))
        ease_factor = max(_MIN_EASE_FACTOR, ease_factor)

        return SpacedRepetitionCard(
            ease_factor=ease_factor,
            interval_days=interval_days,
            repetitions=repetitions,
            due_at=now + timedelta(days=interval_days),
        )

    @property
    def is_learned(self) -> bool:
        """True once the ASD-adapted repetition count has been reached."""
        return self.repetitions >= _REPETITIONS_TO_LEARNED


def next_review_priority(cards: list[tuple[int, SpacedRepetitionCard]], now: datetime | None = None) -> list[int]:
    """
    Given a list of (content_item_id, SpacedRepetitionCard) pairs,
    return content_item_ids ordered by review priority: overdue items
    first (most overdue first), then not-yet-due items ordered by
    soonest due date. Used to build "what should this student review
    next?" priority queues.
    """
    now = now or datetime.utcnow()

    def sort_key(pair: tuple[int, SpacedRepetitionCard]) -> tuple[int, float]:
        _, card = pair
        if card.due_at is None:
            return (0, 0.0)  # never reviewed -> highest priority
        overdue_seconds = (now - card.due_at).total_seconds()
        # Negative overdue_seconds sorts less-overdue/not-yet-due items later.
        return (0 if overdue_seconds >= 0 else 1, -overdue_seconds)

    return [content_id for content_id, _ in sorted(cards, key=sort_key)]
