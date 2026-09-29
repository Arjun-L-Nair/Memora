"""
tests/test_ml_pipeline.py

Covers Phase 16 Section 8 (Machine Learning Verification): model
loading, artifact handling, and failure-mode safety for the
Engagement Prediction pipeline.

Isolation note:
    These tests monkeypatch app.ml.model's module-level artifact paths
    and in-process cache to point at a scratch directory
    (tests/_ml_artifacts_scratch/), so they never read, write, or
    corrupt the real backend/app/ml/artifacts/ files used by the
    running dev app. The real cache/paths are restored after each test.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from app.ml import model as ml_model
from app.ml.features import EngagementFeatures
from tests.conftest import auth_header

_SCRATCH_DIR = Path(__file__).parent / "_ml_artifacts_scratch"


@pytest.fixture(autouse=True)
def _isolated_ml_artifacts(monkeypatch):
    """Redirects ml/model.py's artifact paths + in-process cache to a
    scratch directory for the duration of each test in this file, and
    restores everything afterward so the real dev artifacts are never
    touched."""
    _SCRATCH_DIR.mkdir(exist_ok=True)
    monkeypatch.setattr(ml_model, "_MODEL_PATH", _SCRATCH_DIR / "engagement_model.joblib")
    monkeypatch.setattr(ml_model, "_SCALER_PATH", _SCRATCH_DIR / "engagement_scaler.joblib")
    monkeypatch.setattr(ml_model, "_cached_model", None)
    monkeypatch.setattr(ml_model, "_cached_scaler", None)
    yield
    shutil.rmtree(_SCRATCH_DIR, ignore_errors=True)


def _sample_features(**overrides) -> EngagementFeatures:
    defaults = dict(
        quiz_accuracy=0.75,
        time_spent_seconds=300,
        idle_time_seconds=15,
        hint_usage_count=1,
        retry_count=0,
    )
    defaults.update(overrides)
    return EngagementFeatures(**defaults)


# --- Model loading / artifact handling ---


def test_trains_and_persists_when_artifacts_missing():
    assert not ml_model._MODEL_PATH.exists()
    assert not ml_model._SCALER_PATH.exists()

    result = ml_model.predict_engagement(_sample_features())

    assert result.engagement_label in ("Low", "Medium", "High")
    assert 0.0 <= result.engagement_score <= 1.0
    assert len(result.explanation) > 0
    # Training must have persisted both artifacts for reuse.
    assert ml_model._MODEL_PATH.exists()
    assert ml_model._SCALER_PATH.exists()


def test_loads_from_disk_on_second_call_without_retraining(monkeypatch):
    ml_model.predict_engagement(_sample_features())  # trains + saves
    ml_model._cached_model = None
    ml_model._cached_scaler = None

    train_calls = []
    original_train = ml_model._train_new_model

    def _spy_train():
        train_calls.append(1)
        return original_train()

    monkeypatch.setattr(ml_model, "_train_new_model", _spy_train)

    ml_model.predict_engagement(_sample_features())
    assert train_calls == [], "Should load existing artifacts, not retrain, on second call."


def test_partial_artifacts_triggers_full_retrain():
    """Only the model file present, scaler missing: must retrain BOTH
    (never load a mismatched model/scaler pair)."""
    ml_model.predict_engagement(_sample_features())  # creates both files
    ml_model._SCALER_PATH.unlink()
    ml_model._cached_model = None
    ml_model._cached_scaler = None

    result = ml_model.predict_engagement(_sample_features())
    assert result.engagement_label in ("Low", "Medium", "High")
    assert ml_model._SCALER_PATH.exists()  # retrained and re-saved


def test_corrupted_model_artifact_raises_cleanly_not_silently_wrong():
    """
    A corrupted artifact must not silently produce a bogus prediction —
    it must fail loudly (raise) so the router/global handler turns it
    into a clean error response, rather than persisting a meaningless
    engagement_label to the database. See Ticket H investigation notes:
    at the HTTP layer this surfaces as a generic 500 with no internal
    details leaked, and the rest of the application keeps working —
    confirmed separately via a live TestClient call.
    """
    ml_model._MODEL_PATH.write_bytes(b"not a real joblib file")
    ml_model._SCALER_PATH.write_bytes(b"not a real joblib file either")

    with pytest.raises(Exception):
        ml_model.predict_engagement(_sample_features())


# --- Edge-case / malformed input handling ---


def test_predict_with_no_quiz_attempt_yet(client, teacher_token, seeded_session):
    """
    A session with no QuizAttempt yet has quiz_accuracy=None. The
    engagement-prediction endpoint must handle this via the neutral
    default in features.py, not crash.
    """
    response = client.post(
        f"/engagement-predictions/{seeded_session['id']}/generate",
        headers=auth_header(teacher_token),
    )
    assert response.status_code == 201
    body = response.json()
    assert body["quiz_accuracy"] is None  # truthful snapshot, not the neutral substitute
    assert body["engagement_label"] in ("Low", "Medium", "High")


def test_predict_with_all_zero_behavior_metrics():
    result = ml_model.predict_engagement(
        _sample_features(
            quiz_accuracy=0.0,
            time_spent_seconds=0,
            idle_time_seconds=0,
            hint_usage_count=0,
            retry_count=0,
        )
    )
    assert result.engagement_label in ("Low", "Medium", "High")
    assert len(result.explanation) > 0


def test_predict_with_all_none_optional_fields():
    result = ml_model.predict_engagement(
        EngagementFeatures(
            quiz_accuracy=None,
            time_spent_seconds=None,
            idle_time_seconds=None,
            hint_usage_count=None,
            retry_count=None,
        )
    )
    assert result.engagement_label in ("Low", "Medium", "High")


def test_predict_with_extreme_large_values():
    result = ml_model.predict_engagement(
        _sample_features(
            time_spent_seconds=10_000_000,
            idle_time_seconds=9_999_999,
            hint_usage_count=100_000,
            retry_count=100_000,
        )
    )
    assert result.engagement_label in ("Low", "Medium", "High")
    assert 0.0 <= result.engagement_score <= 1.0


def test_predict_with_perfect_engagement_signals():
    result = ml_model.predict_engagement(
        _sample_features(
            quiz_accuracy=1.0, time_spent_seconds=600, idle_time_seconds=0,
            hint_usage_count=0, retry_count=0,
        )
    )
    assert result.engagement_label in ("Low", "Medium", "High")


def test_predict_with_worst_engagement_signals():
    result = ml_model.predict_engagement(
        _sample_features(
            quiz_accuracy=0.0, time_spent_seconds=5, idle_time_seconds=600,
            hint_usage_count=20, retry_count=20,
        )
    )
    assert result.engagement_label in ("Low", "Medium", "High")


# --- Explanation / determinism ---


def test_prediction_is_deterministic_for_identical_input():
    features = _sample_features()
    first = ml_model.predict_engagement(features)
    second = ml_model.predict_engagement(features)
    assert first.engagement_label == second.engagement_label
    assert first.engagement_score == second.engagement_score
    assert first.explanation == second.explanation


def test_explanation_always_present_and_nonempty_across_varied_inputs():
    for features in (
        _sample_features(),
        _sample_features(quiz_accuracy=None),
        _sample_features(time_spent_seconds=0, idle_time_seconds=0),
    ):
        result = ml_model.predict_engagement(features)
        assert isinstance(result.explanation, str)
        assert len(result.explanation) > 0
        assert result.engagement_label in result.explanation


# --- Held-out evaluation (ml/evaluation.py) ---


def test_evaluate_model_returns_plausible_metrics():
    """
    evaluate_model() must run a real stratified 80/20 split, fit a
    throwaway classifier, and report metrics computed on the held-out
    test portion — not fabricated or hardcoded numbers.
    """
    from app.ml.evaluation import evaluate_model

    result = evaluate_model()

    assert result.total_samples == 1200
    assert result.train_samples == 960
    assert result.test_samples == 240
    assert result.train_samples + result.test_samples == result.total_samples

    # A real accuracy score must be a valid probability, and given the
    # dataset's deliberately learnable structure, comfortably above
    # chance level (1/3 for a balanced 3-class problem).
    assert 0.0 <= result.overall_accuracy <= 1.0
    assert result.overall_accuracy > 0.5

    # All three engagement labels should appear in a 60-sample stratified
    # test split of a dataset designed to have all three represented.
    assert set(result.confusion_matrix_labels) == {"Low", "Medium", "High"}
    assert len(result.per_class) == 3

    for pc in result.per_class:
        assert 0.0 <= pc.precision <= 1.0
        assert 0.0 <= pc.recall <= 1.0
        assert 0.0 <= pc.f1_score <= 1.0
        assert pc.support >= 0

    # Confusion matrix must be square and match the label count.
    n = len(result.confusion_matrix_labels)
    assert len(result.confusion_matrix) == n
    assert all(len(row) == n for row in result.confusion_matrix)


def test_evaluate_model_is_deterministic():
    """Same fixed random_state throughout -> identical metrics every call."""
    from app.ml.evaluation import evaluate_model

    first = evaluate_model()
    second = evaluate_model()
    assert first.overall_accuracy == second.overall_accuracy
    assert first.confusion_matrix == second.confusion_matrix


def test_evaluate_model_does_not_affect_production_model_cache():
    """
    Calling evaluate_model() must never touch app.ml.model's cached
    production model/scaler — it trains its own throwaway classifier
    entirely separately.
    """
    from app.ml.evaluation import evaluate_model

    features = _sample_features()
    before = ml_model.predict_engagement(features)

    evaluate_model()

    after = ml_model.predict_engagement(features)
    assert before.engagement_label == after.engagement_label
    assert before.engagement_score == after.engagement_score


def test_model_evaluation_endpoint_requires_teacher_auth(client):
    response = client.get("/engagement-predictions/model/evaluation")
    assert response.status_code == 401


def test_model_evaluation_endpoint_returns_metrics(client, teacher_token):
    from tests.conftest import auth_header

    response = client.get(
        "/engagement-predictions/model/evaluation", headers=auth_header(teacher_token)
    )
    assert response.status_code == 200
    body = response.json()
    assert body["total_samples"] == 1200
    assert 0.0 <= body["overall_accuracy"] <= 1.0
    assert len(body["per_class"]) == 3
    assert "notes" in body and len(body["notes"]) > 0


def test_model_evaluation_endpoint_rejects_student(client, student_token):
    from tests.conftest import auth_header

    response = client.get(
        "/engagement-predictions/model/evaluation", headers=auth_header(student_token)
    )
    # This codebase's auth convention (see api/deps.py) returns 401 for
    # any role mismatch, not 403 — a student token is structurally
    # valid but for the wrong role, which is treated identically to an
    # invalid/expired token.
    assert response.status_code == 401
