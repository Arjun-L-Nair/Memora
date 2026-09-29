"""
ml/dataset.py

Deterministic synthetic training dataset for Engagement Prediction.

Used in two situations:
    1. As the guaranteed fallback when the real datasets in
       data_loader.py can't be reached (no network / first run before
       `python -m app.ml.data_loader --refresh` has been executed).
    2. Blended with real-dataset-derived rows (model.py) when the real
       caches ARE available, so the ensemble sees both.

Determinism:
    - A fixed random seed (42) is used for the feature-value grid, so
      the same dataset is generated every time from a clean state.
    - Labels are assigned by a fixed, explicit rule function, not by
      any randomness — two runs of this module always produce the
      exact same (X, y) pair.

This generates the full 18-feature vector (see ml/features.py
FEATURE_ORDER) — the original 5 session-level indicators plus
synthetic-but-plausible temporal/behavioral/historical/sensory values,
correlated with the label in a way that gives the ensemble model
something real to learn from feature importances on.
"""

from __future__ import annotations

import numpy as np

from app.ml.features import FEATURE_ORDER

_RANDOM_SEED = 42
_NUM_SAMPLES = 1200  # up from 300: gives 60/20/20 split enough rows per class


def _label_from_raw(row: dict[str, float]) -> str:
    """
    Deterministic, explainable labeling rule used ONLY to construct
    synthetic training labels — never the prediction mechanism itself.

    A weighted-score heuristic across session, temporal, behavioral,
    and historical signals. Thresholds were calibrated against the
    generated feature distribution for a roughly balanced 3-way split.
    """
    idle_ratio = (
        row["idle_time_seconds"] / row["time_spent_seconds"]
        if row["time_spent_seconds"] > 0
        else 1.0
    )

    score = (
        row["quiz_accuracy"] * 0.30
        + (1 - idle_ratio) * 0.20
        - (row["hint_usage_count"] / 5) * 0.05
        - (row["retry_count"] / 5) * 0.05
        + row["rolling_avg_accuracy_5"] * 0.15
        + max(0.0, row["engagement_trend_slope"]) * 0.10
        - row["hint_before_answer_ratio"] * 0.05
        + (1 - min(row["days_since_last_session"] / 14.0, 1.0)) * 0.10
        + min(row["sessions_this_week"] / 5.0, 1.0) * 0.05
    )

    if score >= 0.55:
        return "High"
    if score <= 0.38:
        return "Low"
    return "Medium"


def generate_synthetic_dataset() -> tuple[list[list[float]], list[str]]:
    """
    Generate a deterministic synthetic (X, y) training set spanning
    all 18 features in FEATURE_ORDER.

    Returns:
        X: list of feature vectors, in FEATURE_ORDER.
        y: list of engagement_label strings ("Low"/"Medium"/"High").
    """
    rng = np.random.default_rng(_RANDOM_SEED)
    n = _NUM_SAMPLES

    quiz_accuracy = rng.uniform(0.0, 1.0, n)
    time_spent_seconds = rng.uniform(30, 1800, n)
    idle_time_seconds = rng.uniform(0, 900, n)
    hint_usage_count = rng.integers(0, 6, n)
    retry_count = rng.integers(0, 6, n)

    session_hour_of_day = rng.integers(6, 22, n)
    day_of_week = rng.integers(0, 7, n)
    sessions_this_week = rng.integers(0, 8, n)
    days_since_last_session = rng.uniform(0, 21, n)

    avg_answer_change_rate = rng.uniform(0.0, 1.0, n)
    hint_before_answer_ratio = rng.uniform(0.0, 1.0, n)
    time_per_question_seconds = rng.uniform(5, 180, n)

    rolling_avg_accuracy_5 = np.clip(quiz_accuracy + rng.normal(0, 0.1, n), 0.0, 1.0)
    engagement_trend_slope = rng.normal(0.0, 0.15, n)
    difficulty_progression_rate = rng.uniform(-0.2, 0.2, n)

    preferred_mode_encoded = rng.integers(0, 4, n).astype(float)
    sensory_sensitivity_score = rng.uniform(0.0, 1.0, n)
    attention_span_minutes = rng.integers(5, 45, n)

    X: list[list[float]] = []
    y: list[str] = []
    for i in range(n):
        row = {
            "quiz_accuracy": float(quiz_accuracy[i]),
            "time_spent_seconds": float(time_spent_seconds[i]),
            "idle_time_seconds": float(idle_time_seconds[i]),
            "hint_usage_count": float(hint_usage_count[i]),
            "retry_count": float(retry_count[i]),
            "session_hour_of_day": float(session_hour_of_day[i]),
            "day_of_week": float(day_of_week[i]),
            "sessions_this_week": float(sessions_this_week[i]),
            "days_since_last_session": float(days_since_last_session[i]),
            "avg_answer_change_rate": float(avg_answer_change_rate[i]),
            "hint_before_answer_ratio": float(hint_before_answer_ratio[i]),
            "time_per_question_seconds": float(time_per_question_seconds[i]),
            "rolling_avg_accuracy_5": float(rolling_avg_accuracy_5[i]),
            "engagement_trend_slope": float(engagement_trend_slope[i]),
            "difficulty_progression_rate": float(difficulty_progression_rate[i]),
            "preferred_mode_encoded": float(preferred_mode_encoded[i]),
            "sensory_sensitivity_score": float(sensory_sensitivity_score[i]),
            "attention_span_minutes": float(attention_span_minutes[i]),
        }
        label = _label_from_raw(row)
        X.append([row[name] for name in FEATURE_ORDER])
        y.append(label)

    assert len(X[0]) == len(FEATURE_ORDER)
    return X, y
