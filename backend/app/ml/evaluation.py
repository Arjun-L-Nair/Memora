"""
ml/evaluation.py

Held-out evaluation for the Engagement Prediction ensemble
(Memora ML overhaul, Component 1).

This module answers the question the production model pipeline
(model.py) cannot answer about itself: "how accurate is this model,
actually?" model.py trains its deployed model on the full training
split for maximum use of available data; this module does its own
stratified train/test split, fits a throwaway model on the train
portion only, and reports metrics computed on the held-out test
portion — an honest, unbiased estimate.

Determinism: the split, the throwaway models, and therefore every
reported metric are deterministic (fixed random_state=42 throughout).

`evaluate_model()` keeps its original return shape (ModelEvaluationResult)
for backward compatibility with the existing /model/evaluation endpoint
and test suite — it now evaluates the ensemble instead of the retired
single DecisionTree, but callers see the same fields.

`compare_models()` is new: it fits DecisionTree, RandomForest,
GradientBoosting, and the deployed VotingClassifier ensemble side by
side and reports accuracy/F1/ROC-AUC for each, plus per-model
confusion matrices — the "model comparison table" and "ROC-AUC /
precision-recall" requirements from the implementation plan.
"""

from __future__ import annotations

import numpy as np
from pydantic import BaseModel
from sklearn.ensemble import GradientBoostingClassifier, RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    confusion_matrix,
    f1_score,
    roc_auc_score,
)
from sklearn.model_selection import StratifiedKFold, cross_val_score, train_test_split
from sklearn.preprocessing import StandardScaler, label_binarize
from sklearn.tree import DecisionTreeClassifier

from app.ml.dataset import generate_synthetic_dataset
from app.ml.model import _build_ensemble

_RANDOM_STATE = 42
_TEST_SIZE = 0.2  # 80/20 split for evaluate_model(); compare_models() uses 60/20/20


class PerClassMetrics(BaseModel):
    label: str
    precision: float
    recall: float
    f1_score: float
    support: int


class ModelEvaluationResult(BaseModel):
    """
    Held-out evaluation metrics for the engagement prediction model's
    current architecture (ensemble + StandardScaler), computed on a
    stratified 80/20 split of the training dataset. Not the metrics of
    the exact model object currently deployed (which trains on the
    full 60% training split) — see module docstring.
    """

    total_samples: int
    train_samples: int
    test_samples: int
    overall_accuracy: float
    per_class: list[PerClassMetrics]
    confusion_matrix: list[list[int]]
    confusion_matrix_labels: list[str]
    notes: str


class ModelComparisonEntry(BaseModel):
    model_name: str
    accuracy: float
    macro_f1: float
    roc_auc_ovr: float | None
    cv_accuracy_mean: float
    cv_accuracy_std: float
    confusion_matrix: list[list[int]]


class ModelComparisonResult(BaseModel):
    labels: list[str]
    models: list[ModelComparisonEntry]
    notes: str


def evaluate_model() -> ModelEvaluationResult:
    """
    Run a stratified 80/20 train/test split on the training dataset,
    fit a fresh (throwaway) copy of the ensemble on the train portion
    only, and return accuracy/precision/recall/F1 (per class and
    overall) plus a confusion matrix computed on the held-out test
    portion.

    Safe to call repeatedly (e.g. from an API endpoint) — does not
    touch or invalidate the cached production model/scaler in
    model.py.
    """
    X, y = generate_synthetic_dataset()

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=_TEST_SIZE, random_state=_RANDOM_STATE, stratify=y
    )

    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)
    X_test_scaled = scaler.transform(X_test)

    model = _build_ensemble()
    model.fit(X_train_scaled, y_train)

    y_pred = model.predict(X_test_scaled)
    accuracy = accuracy_score(y_test, y_pred)

    labels = sorted(set(y_train) | set(y_test))

    report = classification_report(y_test, y_pred, labels=labels, output_dict=True, zero_division=0)
    per_class = [
        PerClassMetrics(
            label=label,
            precision=report[label]["precision"],
            recall=report[label]["recall"],
            f1_score=report[label]["f1-score"],
            support=int(report[label]["support"]),
        )
        for label in labels
    ]

    cm = confusion_matrix(y_test, y_pred, labels=labels)

    return ModelEvaluationResult(
        total_samples=len(X),
        train_samples=len(X_train),
        test_samples=len(X_test),
        overall_accuracy=accuracy,
        per_class=per_class,
        confusion_matrix=cm.tolist(),
        confusion_matrix_labels=labels,
        notes=(
            "Evaluated on a stratified 80/20 split of the synthetic "
            "training dataset, not on real session data. This is an "
            "honest estimate of how well the current feature set and "
            "ensemble architecture (RandomForest + GradientBoosting + "
            "LogisticRegression, soft voting) recovers the rule-based "
            "synthetic labels, not a guarantee of real-world accuracy. "
            "The deployed model itself is trained on the full 60% "
            "training split (see ml/model.py) — these metrics describe "
            "the modeling approach's generalization behavior, not the "
            "literal deployed model object."
        ),
    )


def compare_models() -> ModelComparisonResult:
    """
    Fit DecisionTree, RandomForest, GradientBoosting, and the deployed
    VotingClassifier ensemble on the same stratified 60/20/20 split
    (train/val/test — val is folded into train here since this
    function only needs a single held-out test set, not a separate
    tuning set), and report accuracy / macro-F1 / one-vs-rest ROC-AUC
    / 5-fold CV accuracy / confusion matrix for each, for the model
    comparison table required by the implementation plan.
    """
    X, y = generate_synthetic_dataset()
    X = np.array(X)
    y = np.array(y)

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=_RANDOM_STATE, stratify=y
    )

    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)
    X_test_scaled = scaler.transform(X_test)

    labels = sorted(set(y_train) | set(y_test))
    y_test_binarized = label_binarize(y_test, classes=labels)

    candidates: dict[str, object] = {
        "DecisionTree": DecisionTreeClassifier(random_state=_RANDOM_STATE),
        "RandomForest": RandomForestClassifier(n_estimators=200, max_depth=8, random_state=_RANDOM_STATE),
        "GradientBoosting": GradientBoostingClassifier(n_estimators=150, max_depth=3, random_state=_RANDOM_STATE),
        "LogisticRegression": LogisticRegression(max_iter=1000, random_state=_RANDOM_STATE),
        "VotingEnsemble (deployed)": _build_ensemble(),
    }

    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=_RANDOM_STATE)
    entries: list[ModelComparisonEntry] = []

    for name, estimator in candidates.items():
        estimator.fit(X_train_scaled, y_train)
        y_pred = estimator.predict(X_test_scaled)

        accuracy = accuracy_score(y_test, y_pred)
        macro_f1 = f1_score(y_test, y_pred, labels=labels, average="macro", zero_division=0)

        roc_auc: float | None
        try:
            y_proba = estimator.predict_proba(X_test_scaled)
            roc_auc = float(roc_auc_score(y_test_binarized, y_proba, multi_class="ovr", average="macro"))
        except Exception:
            roc_auc = None

        cv_scores = cross_val_score(estimator, X_train_scaled, y_train, cv=cv, scoring="accuracy")
        cm = confusion_matrix(y_test, y_pred, labels=labels)

        entries.append(
            ModelComparisonEntry(
                model_name=name,
                accuracy=float(accuracy),
                macro_f1=float(macro_f1),
                roc_auc_ovr=roc_auc,
                cv_accuracy_mean=float(cv_scores.mean()),
                cv_accuracy_std=float(cv_scores.std()),
                confusion_matrix=cm.tolist(),
            )
        )

    return ModelComparisonResult(
        labels=labels,
        models=entries,
        notes=(
            "All models evaluated on the same stratified 80/20 "
            "train/test split of the synthetic dataset, with 5-fold CV "
            "accuracy computed on the training portion. "
            "'VotingEnsemble (deployed)' is the same architecture as "
            "the model actually served by ml/model.py."
        ),
    )
