"""
services/student_learning_service.py

Business logic for the student-facing learning workflow (Master
Specification Section 5, 6: Today's Learning, Progress Tracking).

"Today's Learning" policy (specification silent; explicit policy
proposed and confirmed before implementation):
    - Shows sessions with status == "started" only (current, actionable
      work) — not completed or abandoned sessions.
    - Ordered most-recently-started first (started_at DESC).
    A separate, general session-history function is also provided for
    "Progress Tracking" (Section 6), returning all statuses in the same
    order.

Completing/abandoning a session as the student:
    Reuses the exact status-transition logic already defined in
    learning_session_service.py (frozen, Phase 7) — specifically
    _apply_end_metrics() and the InvalidSessionStateError exception —
    rather than duplicating that logic. Only the ownership check
    differs (student_id match here, vs. teacher-via-plan there), reused
    from quiz_service.py's _get_owned_session_for_student(), which
    already implements exactly this check.

Phase 15 Module 4 — Adaptive Content Recommendation (student-facing):
    get_recommended_content_for_student() is a thin authorization
    wrapper, not a second recommendation engine. It:
        1. Confirms the target LearningPlan is ASSIGNED to the
           AUTHENTICATED student (via PlanAssignment, or the plan's
           legacy student_id column — see the plan-reuse restructure)
           — the student's own id, always taken from get_current_student
           by the router, never from client input.
        2. Delegates the actual recommendation to
           app.services.learning_content_service.recommend_learning_content_for_student()
           (Module 3, frozen) — passing that plan's own teacher_id
           (already confirmed to be this student's real teacher via
           step 1) so Module 3's existing teacher-ownership check
           passes naturally. The difficulty-ranking logic itself is
           never reimplemented here.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session as DBSession

from app.models import LearningContent, LearningPlan, LearningSession, PlanAssignment
from app.schemas.learning_session import LearningSessionEndRequest
from app.services.learning_content_service import (
    ContentRecommendationResult,
    recommend_learning_content_for_student,
)
from app.services.learning_session_service import InvalidSessionStateError, _apply_end_metrics
from app.services.quiz_service import (
    LearningSessionNotFoundError,
    _get_owned_session_for_student,
)

logger = logging.getLogger(__name__)

__all__ = [
    "LearningSessionNotFoundError",
    "InvalidSessionStateError",
    "LearningPlanNotFoundForStudentError",
    "get_todays_learning",
    "get_all_sessions_for_student",
    "complete_session_as_student",
    "abandon_session_as_student",
    "get_recommended_content_for_student",
    "get_content_for_session",
]


class LearningPlanNotFoundForStudentError(Exception):
    """Raised when a plan does not exist, or does not belong to the requesting student."""


def get_todays_learning(db: DBSession, student_id: int) -> list[LearningSession]:
    """
    "Today's Learning": the student's currently in-progress sessions
    (status == "started"), most recently started first.
    """
    result = db.execute(
        select(LearningSession)
        .where(
            LearningSession.student_id == student_id,
            LearningSession.status == "started",
        )
        .order_by(LearningSession.started_at.desc())
    )
    return list(result.scalars().all())


def get_content_for_session(
    db: DBSession, student_id: int, session_id: int
) -> LearningContent:
    """
    Get the exact LearningContent tied to one of the student's own
    sessions (session.learning_content_id) — NOT a re-derived
    recommendation.

    This exists because a session's content is chosen once, explicitly,
    by the teacher at session-creation time (LearningSession.learning_content_id
    is a required FK, see learning_session_service.create_learning_session).
    The recommendation engine (recommend_learning_content_for_student)
    always returns its single best-ranked match for the plan's current
    difficulty level, which is appropriate when *proposing* what to
    assign next, but is the wrong call once a session already has
    specific content associated with it — using the recommendation here
    would silently substitute a different piece of content (typically
    the lowest-id match) any time a plan has more than one active entry
    at the same difficulty level, hiding whatever the teacher actually
    assigned.

    Raises LearningSessionNotFoundError if the session doesn't exist or
    isn't owned by this student (reusing the same ownership check used
    everywhere else a student acts on their own session).
    """
    session = _get_owned_session_for_student(db, student_id, session_id)

    content = db.get(LearningContent, session.learning_content_id)
    assert content is not None  # guaranteed by the FK set at session creation
    return content


def get_all_sessions_for_student(db: DBSession, student_id: int) -> list[LearningSession]:
    """
    All of the student's sessions, any status, most recently started
    first — supports "Progress Tracking" (Section 6).
    """
    result = db.execute(
        select(LearningSession)
        .where(LearningSession.student_id == student_id)
        .order_by(LearningSession.started_at.desc())
    )
    return list(result.scalars().all())


def complete_session_as_student(
    db: DBSession, student_id: int, session_id: int, payload: LearningSessionEndRequest
) -> LearningSession:
    """
    Mark one of the student's own sessions as completed. Raises
    LearningSessionNotFoundError if the session doesn't exist or isn't
    owned by this student; InvalidSessionStateError if it isn't
    currently "started".

    Automatically generates the session's engagement prediction (and,
    as part of that, runs the difficulty-adjustment rule engine) the
    moment the session completes — this used to be a separate,
    easy-to-forget manual teacher action with no obvious UI entry
    point, which meant engagement data silently never got created in
    practice. Now every completed session gets one automatically, with
    no teacher action required. Prediction failure is logged and
    swallowed rather than raised: a slow/broken ML step must never
    block a student from completing their session, since actually
    finishing the learning loop matters far more than the analytics
    that describe it. A teacher can always regenerate a missing
    prediction later via the existing manual endpoint.
    """
    session = _get_owned_session_for_student(db, student_id, session_id)

    if session.status != "started":
        raise InvalidSessionStateError(
            f"Session {session_id} is '{session.status}', not 'started'."
        )

    session.status = "completed"
    session.completed_at = datetime.now(timezone.utc)
    _apply_end_metrics(session, payload)

    db.commit()
    db.refresh(session)

    try:
        from app.services.engagement_prediction_service import (
            EngagementPredictionAlreadyExistsError,
            generate_engagement_prediction_for_session,
        )

        generate_engagement_prediction_for_session(db, session)
    except EngagementPredictionAlreadyExistsError:
        pass  # already generated somehow (e.g. a retried request) — fine, not an error
    except Exception as exc:  # noqa: BLE001 — deliberately broad, see docstring
        logger.warning(
            "Automatic engagement prediction generation failed for session %s (%s). "
            "Session completion still succeeded; a teacher can generate it manually later.",
            session_id,
            exc,
        )

    return session


def abandon_session_as_student(
    db: DBSession, student_id: int, session_id: int, payload: LearningSessionEndRequest
) -> LearningSession:
    """
    Mark one of the student's own sessions as abandoned. Same
    validation as complete_session_as_student().
    """
    session = _get_owned_session_for_student(db, student_id, session_id)

    if session.status != "started":
        raise InvalidSessionStateError(
            f"Session {session_id} is '{session.status}', not 'started'."
        )

    session.status = "abandoned"
    session.completed_at = datetime.now(timezone.utc)
    _apply_end_metrics(session, payload)

    db.commit()
    db.refresh(session)
    return session


def get_recommended_content_for_student(
    db: DBSession, student_id: int, learning_plan_id: int
) -> ContentRecommendationResult:
    """
    Resolve a difficulty-aware content recommendation for one of the
    AUTHENTICATED student's own learning plans.

    Security: learning_plan_id is checked against the student being
    ASSIGNED to that plan (see PlanAssignment / the plan-reuse
    restructure), or — for any plan created before that restructure —
    the plan's legacy student_id column. A student can never retrieve
    a recommendation for a plan they aren't assigned to, and therefore
    never for another teacher's plan either, since every plan has
    exactly one owning teacher.

    Raises LearningPlanNotFoundForStudentError if the plan does not
    exist or this student is not assigned to it.

    Delegates the actual difficulty-ranking decision entirely to
    app.services.learning_content_service.recommend_learning_content_for_student()
    — this function performs no ranking or matching logic of its own.
    """
    plan = db.execute(
        select(LearningPlan)
        .outerjoin(PlanAssignment, PlanAssignment.learning_plan_id == LearningPlan.id)
        .where(
            LearningPlan.id == learning_plan_id,
            (PlanAssignment.student_id == student_id) | (LearningPlan.student_id == student_id),
        )
    ).scalars().first()

    if plan is None:
        raise LearningPlanNotFoundForStudentError(
            f"Learning plan {learning_plan_id} not found for this student."
        )

    # plan.teacher_id is safe to pass here: step above already proved
    # this student is assigned to this exact plan, so its teacher_id is
    # simply that plan's real, existing owning teacher — not client-
    # supplied, not attacker-controlled. This lets the target function's
    # own teacher-ownership check succeed naturally without a second,
    # parallel authorization implementation.
    return recommend_learning_content_for_student(db, plan.teacher_id, learning_plan_id, student_id)
