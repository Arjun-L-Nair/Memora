"""
ml/early_warning.py

Time-series analysis of per-student engagement trajectories and a
dropout/disengagement risk score (Memora overhaul, Component 4).

Modeled after the pattern OULAD studies use to characterize
disengagement (declining VLE interaction frequency + declining
assessment scores over a rolling window) — see data_loader.py's
load_oulad_vle_interactions() for the real-dataset path; this module
computes the same *kind* of signal directly from in-app
LearningSession/EngagementPrediction history, which is always
available regardless of whether the external OULAD cache could be
downloaded.

Risk score (0-100, higher = more at risk) is a weighted combination
of:
    - engagement trend slope (recent sessions trending down)
    - session frequency trend (fewer sessions per week recently vs. before)
    - quiz accuracy trend
    - days since last session (recency)

This is a transparent, rule-weighted score rather than a black-box
classifier — deliberately, so "why is this student flagged?" always
has a plain-language answer (contributing_factors below), which
matters for a teacher-facing tool making judgments about a vulnerable
student population.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

# Weights sum to 1.0 for interpretability of the final 0-100 score.
_WEIGHT_ENGAGEMENT_TREND = 0.35
_WEIGHT_FREQUENCY_TREND = 0.25
_WEIGHT_ACCURACY_TREND = 0.25
_WEIGHT_RECENCY = 0.15

_RISK_THRESHOLDS = [
    (75, "At Risk"),
    (50, "Needs Attention"),
    (25, "On Track"),
    (0, "Thriving"),
]


@dataclass
class SessionSignal:
    """Minimal per-session data needed for risk scoring, oldest-first not required."""

    created_at: datetime
    engagement_score: float | None  # 0-1, from EngagementPrediction
    quiz_accuracy: float | None  # 0-1


@dataclass
class EarlyWarningResult:
    risk_score: float  # 0-100
    risk_level: str  # "At Risk" / "Needs Attention" / "On Track" / "Thriving"
    contributing_factors: list[str] = field(default_factory=list)


def _trend(values: list[float]) -> float:
    """
    Simple normalized trend: (mean of second half) - (mean of first
    half), clipped to [-1, 1]. Positive = improving, negative =
    declining. Deliberately simple (not a full linear regression) so
    it's easy to explain in a contributing-factor sentence and behaves
    sensibly with very few data points.
    """
    if len(values) < 2:
        return 0.0
    midpoint = len(values) // 2
    first_half = values[:midpoint] or values[:1]
    second_half = values[midpoint:]
    delta = (sum(second_half) / len(second_half)) - (sum(first_half) / len(first_half))
    return max(-1.0, min(1.0, delta))


def compute_risk_score(sessions: list[SessionSignal], now: datetime | None = None) -> EarlyWarningResult:
    """
    Compute a dropout/disengagement risk score from a student's recent
    session history (most recent last, i.e. chronological order).

    Returns a neutral, low-risk-leaning result for a student with too
    little history to say anything meaningful yet, rather than
    flagging a brand-new student as "at risk" purely for lack of data.
    """
    now = now or datetime.utcnow()

    if len(sessions) < 2:
        return EarlyWarningResult(
            risk_score=20.0,
            risk_level="On Track",
            contributing_factors=["Not enough session history yet to assess a trend."],
        )

    ordered = sorted(sessions, key=lambda s: s.created_at)

    engagement_scores = [s.engagement_score for s in ordered if s.engagement_score is not None]
    accuracies = [s.quiz_accuracy for s in ordered if s.quiz_accuracy is not None]

    engagement_trend = _trend(engagement_scores) if engagement_scores else 0.0
    accuracy_trend = _trend(accuracies) if accuracies else 0.0

    # Frequency trend: sessions-per-week in the most recent half of
    # the observed window vs. the earlier half.
    span_days = max((ordered[-1].created_at - ordered[0].created_at).days, 1)
    midpoint_time = ordered[0].created_at + (ordered[-1].created_at - ordered[0].created_at) / 2
    first_half_count = sum(1 for s in ordered if s.created_at <= midpoint_time)
    second_half_count = len(ordered) - first_half_count
    half_span_weeks = max((span_days / 2) / 7, 0.5)
    frequency_trend = max(
        -1.0,
        min(1.0, (second_half_count - first_half_count) / (half_span_weeks * 3)),
    )

    days_since_last = (now - ordered[-1].created_at).total_seconds() / 86400.0
    recency_penalty = max(0.0, min(1.0, days_since_last / 14.0))  # 14+ days = max penalty

    # Convert each [-1, 1] trend into a [0, 1] risk contribution
    # (negative trend / high recency penalty -> higher risk).
    engagement_risk = (1 - engagement_trend) / 2
    frequency_risk = (1 - frequency_trend) / 2
    accuracy_risk = (1 - accuracy_trend) / 2

    risk_score = 100 * (
        _WEIGHT_ENGAGEMENT_TREND * engagement_risk
        + _WEIGHT_FREQUENCY_TREND * frequency_risk
        + _WEIGHT_ACCURACY_TREND * accuracy_risk
        + _WEIGHT_RECENCY * recency_penalty
    )
    risk_score = round(max(0.0, min(100.0, risk_score)), 1)

    risk_level = next(level for threshold, level in _RISK_THRESHOLDS if risk_score >= threshold)

    factors: list[str] = []
    if engagement_trend < -0.15:
        factors.append("Engagement has been trending downward across recent sessions.")
    if frequency_trend < -0.15:
        factors.append("Session frequency has dropped compared to earlier weeks.")
    if accuracy_trend < -0.15:
        factors.append("Quiz accuracy has been trending downward.")
    if days_since_last > 7:
        factors.append(f"No session in the last {int(days_since_last)} days.")
    if not factors:
        factors.append("No significant negative trends detected.")

    return EarlyWarningResult(risk_score=risk_score, risk_level=risk_level, contributing_factors=factors)
