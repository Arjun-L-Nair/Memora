"""
ml/features.py

Feature extraction for Engagement Prediction (Master Specification
Section 7, extended per the Memora ML overhaul).

Two representations are kept distinct:
    - EngagementFeatures: the RAW, possibly-None values, exactly as
      they should be persisted into EngagementPrediction's frozen
      5-column snapshot (quiz_accuracy, time_spent_seconds,
      idle_time_seconds, hint_usage_count, retry_count) — ground
      truth, including NULL quiz_accuracy when no QuizAttempt exists.
      This part of the schema is intentionally left untouched so the
      existing EngagementPrediction table/API contract keeps working.
    - EXTENDED, optional contextual fields (temporal / behavioral /
      historical / sensory) that the service layer may supply when
      available (e.g. from LearningSession history, SensoryProfile,
      LearningPattern). These are never persisted to
      EngagementPrediction; they exist purely to give the model a
      richer input vector. Any field the caller doesn't have is left
      as None and filled with a documented neutral default at
      inference time — the model never breaks on partial context.
    - to_model_input(): converts EngagementFeatures into the full
      18-feature numeric vector consumed by the ensemble model.
"""

from __future__ import annotations

from pydantic import BaseModel

# Neutral defaults used only when a value is unavailable, purely for
# model input — never persisted as the actual snapshot value.
_NEUTRAL_QUIZ_ACCURACY = 0.5
_NEUTRAL_ROLLING_ACCURACY = 0.5
_NEUTRAL_TREND_SLOPE = 0.0
_NEUTRAL_DIFFICULTY_PROGRESSION = 0.0
_NEUTRAL_SENSORY_SENSITIVITY = 0.5

# Fixed feature order used consistently across dataset generation,
# training, and inference. Original 5 (session-level) + 13 new
# (temporal / behavioral / historical / sensory) = 18 total, per the
# implementation plan's Component 1.
FEATURE_ORDER: list[str] = [
    # --- Session-level (original 5, unchanged) ---
    "quiz_accuracy",
    "time_spent_seconds",
    "idle_time_seconds",
    "hint_usage_count",
    "retry_count",
    # --- Temporal ---
    "session_hour_of_day",
    "day_of_week",
    "sessions_this_week",
    "days_since_last_session",
    # --- Behavioral ---
    "avg_answer_change_rate",
    "hint_before_answer_ratio",
    "time_per_question_seconds",
    # --- Historical ---
    "rolling_avg_accuracy_5",
    "engagement_trend_slope",
    "difficulty_progression_rate",
    # --- Sensory ---
    "preferred_mode_encoded",
    "sensory_sensitivity_score",
    "attention_span_minutes",
]

# Encoding for the categorical preferred_mode field, used consistently
# between training-data preprocessing (data_loader.py) and inference.
_PREFERRED_MODE_ENCODING: dict[str, float] = {
    "visual": 0.0,
    "auditory": 1.0,
    "text": 2.0,
    "mixed": 3.0,
}


class EngagementFeatures(BaseModel):
    """
    Raw engagement indicator snapshot for one LearningSession, plus
    optional extended context. Only the first 5 fields are persisted
    to EngagementPrediction; everything else is inference-only.
    """

    # --- Persisted snapshot (frozen schema, unchanged) ---
    quiz_accuracy: float | None
    time_spent_seconds: int | None
    idle_time_seconds: int | None
    hint_usage_count: int | None
    retry_count: int | None

    # --- Extended, optional, NOT persisted ---
    session_hour_of_day: int | None = None
    day_of_week: int | None = None
    sessions_this_week: int | None = None
    days_since_last_session: float | None = None

    avg_answer_change_rate: float | None = None
    hint_before_answer_ratio: float | None = None
    time_per_question_seconds: float | None = None

    rolling_avg_accuracy_5: float | None = None
    engagement_trend_slope: float | None = None
    difficulty_progression_rate: float | None = None

    preferred_mode: str | None = None
    sensory_sensitivity_score: float | None = None
    attention_span_minutes: int | None = None


def to_model_input(features: EngagementFeatures) -> list[float]:
    """
    Convert EngagementFeatures into the fixed-order, 18-element numeric
    vector for the ensemble model. Missing values fall back to
    documented neutral defaults; this affects only the vector returned
    here, never the raw EngagementFeatures object or anything
    persisted to the database.
    """
    preferred_mode_encoded = _PREFERRED_MODE_ENCODING.get(
        (features.preferred_mode or "mixed").lower(), _PREFERRED_MODE_ENCODING["mixed"]
    )

    return [
        # session-level
        features.quiz_accuracy if features.quiz_accuracy is not None else _NEUTRAL_QUIZ_ACCURACY,
        float(features.time_spent_seconds or 0),
        float(features.idle_time_seconds or 0),
        float(features.hint_usage_count or 0),
        float(features.retry_count or 0),
        # temporal
        float(features.session_hour_of_day if features.session_hour_of_day is not None else 12),
        float(features.day_of_week if features.day_of_week is not None else 0),
        float(features.sessions_this_week or 0),
        float(features.days_since_last_session if features.days_since_last_session is not None else 0.0),
        # behavioral
        float(features.avg_answer_change_rate or 0.0),
        float(features.hint_before_answer_ratio or 0.0),
        float(features.time_per_question_seconds or 0.0),
        # historical
        float(
            features.rolling_avg_accuracy_5
            if features.rolling_avg_accuracy_5 is not None
            else _NEUTRAL_ROLLING_ACCURACY
        ),
        float(
            features.engagement_trend_slope
            if features.engagement_trend_slope is not None
            else _NEUTRAL_TREND_SLOPE
        ),
        float(
            features.difficulty_progression_rate
            if features.difficulty_progression_rate is not None
            else _NEUTRAL_DIFFICULTY_PROGRESSION
        ),
        # sensory
        preferred_mode_encoded,
        float(
            features.sensory_sensitivity_score
            if features.sensory_sensitivity_score is not None
            else _NEUTRAL_SENSORY_SENSITIVITY
        ),
        float(features.attention_span_minutes or 15),
    ]

