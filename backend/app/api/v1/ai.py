"""
api/v1/ai.py

AI router: Engagement Prediction and Adaptive Suggestions (Master
Specification Section 6, 7, 10).

Named/tagged "AI" per the reserved placeholder in main.py, whose own
tag description is "Engagement prediction and adaptive suggestions" —
this file is the single home for both features; no other AI-tagged
router exists.

Teacher-only throughout (get_current_teacher, frozen Phase 4) — no
automatic generation hook and no student-facing endpoint here.

This router contains no business logic and never touches the ML layer
or the rule engine directly; it only parses requests, calls the
appropriate service (engagement_prediction_service.py or
adaptive_suggestion_service.py), translates service-layer exceptions
into HTTP responses, and returns schemas.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_teacher
from app.database import get_db
from app.ml.evaluation import ModelEvaluationResult, evaluate_model
from app.models import Teacher
from app.schemas.adaptive_suggestion import AdaptiveSuggestionResponse
from app.schemas.engagement_prediction import EngagementPredictionResponse
from app.services.adaptive_suggestion_service import get_adaptive_suggestion
from app.services.engagement_prediction_service import (
    EngagementPredictionAlreadyExistsError,
    EngagementPredictionNotFoundError,
    LearningSessionNotFoundError,
    generate_engagement_prediction,
    get_engagement_prediction_for_teacher,
)

router = APIRouter(prefix="/engagement-predictions", tags=["AI"])

_SESSION_NOT_FOUND = HTTPException(
    status_code=status.HTTP_404_NOT_FOUND,
    detail="Learning session not found.",
)
_PREDICTION_NOT_FOUND = HTTPException(
    status_code=status.HTTP_404_NOT_FOUND,
    detail="Engagement prediction not found.",
)


@router.post(
    "/{learning_session_id}/generate",
    response_model=EngagementPredictionResponse,
    status_code=status.HTTP_201_CREATED,
)
def generate_engagement_prediction_endpoint(
    learning_session_id: int,
    teacher: Teacher = Depends(get_current_teacher),
    db: Session = Depends(get_db),
) -> EngagementPredictionResponse:
    """
    Generate and persist an engagement prediction for one of the
    teacher's own learning sessions. Returns 409 if a prediction
    already exists for this session.
    """
    try:
        prediction = generate_engagement_prediction(db, teacher.id, learning_session_id)
    except LearningSessionNotFoundError:
        raise _SESSION_NOT_FOUND
    except EngagementPredictionAlreadyExistsError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        )

    return EngagementPredictionResponse.model_validate(prediction)


@router.get("/{prediction_id}", response_model=EngagementPredictionResponse)
def get_engagement_prediction_endpoint(
    prediction_id: int,
    teacher: Teacher = Depends(get_current_teacher),
    db: Session = Depends(get_db),
) -> EngagementPredictionResponse:
    """Get an engagement prediction owned by the authenticated teacher."""
    try:
        prediction = get_engagement_prediction_for_teacher(db, teacher.id, prediction_id)
    except EngagementPredictionNotFoundError:
        raise _PREDICTION_NOT_FOUND

    return EngagementPredictionResponse.model_validate(prediction)


@router.get(
    "/{learning_session_id}/adaptive-suggestion",
    response_model=AdaptiveSuggestionResponse,
)
def get_adaptive_suggestion_endpoint(
    learning_session_id: int,
    teacher: Teacher = Depends(get_current_teacher),
    db: Session = Depends(get_db),
) -> AdaptiveSuggestionResponse:
    """
    Get a rule-based Adaptive Suggestion for one of the teacher's own
    learning sessions, derived from its already-generated engagement
    prediction. Stateless — computed fresh on every call, nothing is
    persisted. Returns 404 if no engagement prediction exists yet for
    this session (generate one first via
    POST /engagement-predictions/{learning_session_id}/generate).
    """
    try:
        suggestion = get_adaptive_suggestion(db, teacher.id, learning_session_id)
    except LearningSessionNotFoundError:
        raise _SESSION_NOT_FOUND
    except EngagementPredictionNotFoundError:
        raise _PREDICTION_NOT_FOUND

    return suggestion


@router.get("/model/evaluation", response_model=ModelEvaluationResult)
def get_model_evaluation_endpoint(
    teacher: Teacher = Depends(get_current_teacher),
) -> ModelEvaluationResult:
    """
    Held-out evaluation metrics (accuracy, per-class precision/recall/
    F1, confusion matrix) for the engagement prediction model's
    architecture, computed via a stratified 80/20 train/test split of
    the synthetic training dataset. Any authenticated teacher may view
    this — it's model diagnostics, not student-specific data, and is
    intended for transparency about how the AI component works (Master
    Specification Section 7: "every recommendation should be
    explainable" extends naturally to the model's own reported
    performance, not just individual predictions).

    Computed fresh on every call (fast — 300 samples, single decision
    tree) rather than cached, so it always reflects the current
    ml/dataset.py and ml/evaluation.py code exactly.
    """
    return evaluate_model()
