"""
ml/model.py

Model loading, training, and prediction pipeline for Engagement
Prediction — ensemble version (Memora ML overhaul, Component 1).

This is the ONLY module the service layer is allowed to depend on for
anything ML-related — it hides everything else (dataset generation,
scaler, ensemble classifier, joblib persistence) behind a single
function, predict_engagement(). If the model implementation changes
later, only this file changes.

Architecture:
    A soft-voting VotingClassifier over three base estimators:
      - RandomForestClassifier   (handles nonlinear feature interactions)
      - GradientBoostingClassifier (sequential error-correction)
      - LogisticRegression        (a calibrated, linear baseline)
    Soft voting averages predicted class probabilities across the
    three, which is both more stable than any single model and gives
    meaningful confidence scores (unlike hard voting).

Determinism:
    - Every estimator is constructed with random_state=42.
    - The synthetic dataset (ml/dataset.py) is itself deterministic.
    - Inference on a given input always produces the same output.

Validation:
    train_or_load_model() performs a stratified 60/20/20 train/val/test
    split and 5-fold cross-validation on the training split at fit
    time; see evaluation.py for the fuller metrics report used for
    academic write-ups. This module logs a one-line CV summary so a
    developer running the app for the first time can sanity-check the
    model without needing to run evaluation.py separately.

Persistence:
    Model and scaler are saved via joblib under app/ml/artifacts/. If
    both files exist, they are loaded directly (no retraining). If
    either is missing, a fresh dataset is generated, the scaler and
    ensemble are fit, and both are saved for future use.
"""

from __future__ import annotations

import logging
from pathlib import Path

import joblib
import numpy as np
from pydantic import BaseModel
from sklearn.ensemble import (
    GradientBoostingClassifier,
    RandomForestClassifier,
    VotingClassifier,
)
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import StratifiedKFold, cross_val_score, train_test_split
from sklearn.preprocessing import StandardScaler

from app.ml.dataset import generate_synthetic_dataset
from app.ml.features import FEATURE_ORDER, EngagementFeatures, to_model_input

logger = logging.getLogger("memora.ml.model")

_ARTIFACTS_DIR = Path(__file__).parent / "artifacts"
_MODEL_PATH = _ARTIFACTS_DIR / "engagement_model.joblib"
_SCALER_PATH = _ARTIFACTS_DIR / "engagement_scaler.joblib"

_RANDOM_STATE = 42

# In-process cache so the model/scaler are loaded from disk at most
# once per process, not on every prediction call.
_cached_model: VotingClassifier | None = None
_cached_scaler: StandardScaler | None = None


class PredictionResult(BaseModel):
    """Output of the prediction pipeline, ready for the service layer to persist."""

    engagement_score: float
    engagement_label: str
    explanation: str


def _build_ensemble() -> VotingClassifier:
    """Construct the (unfitted) soft-voting ensemble of 3 base estimators."""
    random_forest = RandomForestClassifier(
        n_estimators=200,
        max_depth=8,
        random_state=_RANDOM_STATE,
    )
    gradient_boosting = GradientBoostingClassifier(
        n_estimators=150,
        max_depth=3,
        learning_rate=0.1,
        random_state=_RANDOM_STATE,
    )
    logistic_regression = LogisticRegression(
        max_iter=1000,
        random_state=_RANDOM_STATE,
    )
    return VotingClassifier(
        estimators=[
            ("random_forest", random_forest),
            ("gradient_boosting", gradient_boosting),
            ("logistic_regression", logistic_regression),
        ],
        voting="soft",
    )


def _train_new_model() -> tuple[VotingClassifier, StandardScaler]:
    """
    Generate the dataset, perform a stratified 60/20/20 split, run
    5-fold cross-validation on the training portion for a sanity-check
    log line, then fit the final ensemble on the full training split.

    The held-out val/test splits themselves are not persisted here —
    evaluation.py re-derives the same deterministic split (same
    random_state) when a fuller report is needed, so there is exactly
    one source of truth for how the split is constructed.
    """
    X, y = generate_synthetic_dataset()
    X = np.array(X)
    y = np.array(y)

    X_train, X_temp, y_train, y_temp = train_test_split(
        X, y, test_size=0.4, stratify=y, random_state=_RANDOM_STATE
    )
    # X_temp/y_temp further split 50/50 -> 20% val, 20% test overall.
    # (val/test are used by evaluation.py, not needed again here.)

    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)

    model = _build_ensemble()

    try:
        cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=_RANDOM_STATE)
        cv_scores = cross_val_score(model, X_train_scaled, y_train, cv=cv, scoring="accuracy")
        logger.info(
            "Engagement ensemble 5-fold CV accuracy: %.3f +/- %.3f",
            cv_scores.mean(),
            cv_scores.std(),
        )
    except Exception as exc:  # pragma: no cover - CV is diagnostic only
        logger.warning("Cross-validation step failed (%s); continuing to final fit.", exc)

    model.fit(X_train_scaled, y_train)
    return model, scaler


def _save_artifacts(model: VotingClassifier, scaler: StandardScaler) -> None:
    _ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
    joblib.dump(model, _MODEL_PATH)
    joblib.dump(scaler, _SCALER_PATH)


def train_or_load_model() -> tuple[VotingClassifier, StandardScaler]:
    """
    Load the saved model + scaler from disk if both exist; otherwise
    train a new ensemble and save it for future calls/processes.
    """
    global _cached_model, _cached_scaler

    if _cached_model is not None and _cached_scaler is not None:
        return _cached_model, _cached_scaler

    if _MODEL_PATH.exists() and _SCALER_PATH.exists():
        model = joblib.load(_MODEL_PATH)
        scaler = joblib.load(_SCALER_PATH)
    else:
        model, scaler = _train_new_model()
        _save_artifacts(model, scaler)

    _cached_model, _cached_scaler = model, scaler
    return model, scaler


def _get_feature_importances(model: VotingClassifier) -> np.ndarray | None:
    """
    Average feature_importances_ across the tree-based estimators in
    the ensemble (RandomForest, GradientBoosting). LogisticRegression
    doesn't expose feature_importances_ (it has coef_ instead), so it
    is excluded from this particular explanation signal but still
    contributes to the actual prediction via soft voting.
    """
    importances = []
    for name, estimator in model.named_estimators_.items():
        if hasattr(estimator, "feature_importances_"):
            importances.append(estimator.feature_importances_)
    if not importances:
        return None
    return np.mean(importances, axis=0)


def _build_explanation(model: VotingClassifier, features: EngagementFeatures, label: str) -> str:
    """
    Build a human-readable explanation for the prediction, using the
    ensemble's averaged tree-based feature importances to identify
    which indicators most influenced the decision in general, then
    reporting this session's actual values for those indicators.
    """
    importances = _get_feature_importances(model)
    if importances is None:
        return f"Predicted '{label}' engagement based on overall session indicators."

    ranked_indices = np.argsort(importances)[::-1]
    top_two = [FEATURE_ORDER[i] for i in ranked_indices[:2] if importances[i] > 0]

    if not top_two:
        return f"Predicted '{label}' engagement based on overall session indicators."

    raw_values = {
        "quiz_accuracy": features.quiz_accuracy,
        "time_spent_seconds": features.time_spent_seconds,
        "idle_time_seconds": features.idle_time_seconds,
        "hint_usage_count": features.hint_usage_count,
        "retry_count": features.retry_count,
        "session_hour_of_day": features.session_hour_of_day,
        "day_of_week": features.day_of_week,
        "sessions_this_week": features.sessions_this_week,
        "days_since_last_session": features.days_since_last_session,
        "avg_answer_change_rate": features.avg_answer_change_rate,
        "hint_before_answer_ratio": features.hint_before_answer_ratio,
        "time_per_question_seconds": features.time_per_question_seconds,
        "rolling_avg_accuracy_5": features.rolling_avg_accuracy_5,
        "engagement_trend_slope": features.engagement_trend_slope,
        "difficulty_progression_rate": features.difficulty_progression_rate,
        "preferred_mode_encoded": features.preferred_mode,
        "sensory_sensitivity_score": features.sensory_sensitivity_score,
        "attention_span_minutes": features.attention_span_minutes,
    }

    def _format_value(name: str) -> str:
        value = raw_values.get(name)
        return f"{name}=not available" if value is None else f"{name}={value}"

    detail_parts = [_format_value(name) for name in top_two]
    return (
        f"Predicted '{label}' engagement, most influenced by "
        f"{' and '.join(top_two)} (this session: {', '.join(detail_parts)})."
    )


def predict_engagement(features: EngagementFeatures) -> PredictionResult:
    """
    Run the full prediction pipeline for one session's features:
    load-or-train the ensemble, scale the input, predict the label and
    confidence score (soft-voted probability), and build an
    explanation.

    This is the single entry point the service layer should call —
    everything else in this module is an internal implementation
    detail.
    """
    model, scaler = train_or_load_model()

    raw_input = to_model_input(features)
    scaled_input = scaler.transform([raw_input])

    label = model.predict(scaled_input)[0]
    probabilities = model.predict_proba(scaled_input)[0]
    class_index = list(model.classes_).index(label)
    score = float(probabilities[class_index])

    explanation = _build_explanation(model, features, label)

    return PredictionResult(
        engagement_score=score,
        engagement_label=label,
        explanation=explanation,
    )
