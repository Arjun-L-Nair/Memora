"""
services/learning_session_service.py

Business logic for Learning Session assignment and basic lifecycle
tracking (Master Specification Section 5, 6, 10).

Session creation enforces, in order:
    1. The learning plan exists and is owned by the requesting teacher.
    2. student_id is assigned to the plan (see PlanAssignment / the
       plan-reuse restructure) — or matches the plan's legacy
       student_id column, for plans created before that restructure.
    3. The learning content exists, belongs to the SAME plan as the
       session, and is currently active (deactivated content blocks
       new session assignments; existing sessions are never affected).
    4. System-managed fields are computed here, never client-supplied:
       started_at (now), status ("started"), and
       difficulty_level_at_session (snapshotted from the student's
       current_difficulty_level at creation time).

Lifecycle: a session transitions from "started" to either "completed"
or "abandoned" via dedicated actions — never through a generic field
update, consistent with the frozen model's stated design principle that
completed sessions should be treated as read-only history.

Per the confirmed Phase 7 policy, multiple sessions may exist
simultaneously for the same student/plan/content — no uniqueness is
enforced, since neither the specification nor the frozen schema
requires it.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session as DBSession

from app.models import LearningContent, LearningPlan, LearningSession, Student
from app.schemas.learning_session import LearningSessionCreate, LearningSessionEndRequest


class LearningSessionNotFoundError(Exception):
    """Raised when a session does not exist, or its plan is not owned by the requesting teacher."""


class LearningPlanNotOwnedByTeacherError(Exception):
    """Raised when the target learning plan does not exist or is not owned by the requesting teacher."""


class StudentPlanMismatchError(Exception):
    """Raised when student_id does not match the target plan's own student_id."""


class LearningContentNotAvailableError(Exception):
    """Raised when content does not exist, does not belong to the target plan, or is inactive."""


class InvalidSessionStateError(Exception):
    """Raised when attempting to complete/abandon a session that is not currently 'started'."""


def _get_owned_plan(db: DBSession, teacher_id: int, plan_id: int) -> LearningPlan:
    """Shared check: confirm a learning plan exists and is owned by the given teacher."""
    plan = db.execute(
        select(LearningPlan).where(
            LearningPlan.id == plan_id, LearningPlan.teacher_id == teacher_id
        )
    ).scalar_one_or_none()

    if plan is None:
        raise LearningPlanNotOwnedByTeacherError(
            f"Learning plan {plan_id} does not belong to this teacher."
        )

    return plan


def create_learning_session(
    db: DBSession, teacher_id: int, payload: LearningSessionCreate
) -> LearningSession:
    """
    Assign a new learning session: a student engaging with specific
    content, within a specific plan.

    Raises:
        LearningPlanNotOwnedByTeacherError: plan doesn't exist or isn't
            owned by this teacher.
        StudentPlanMismatchError: the student is not assigned to this
            plan (see PlanAssignment / the plan-reuse restructure —
            also accepts the legacy plan.student_id == payload.student_id
            match, for any plan created before that restructure or via
            the old one-step single-student creation path).
        LearningContentNotAvailableError: content doesn't exist, isn't
            part of the given plan, or is inactive.
    """
    plan = _get_owned_plan(db, teacher_id, payload.learning_plan_id)

    is_assigned = any(a.student_id == payload.student_id for a in plan.assignments)
    is_legacy_match = plan.student_id is not None and plan.student_id == payload.student_id

    if not is_assigned and not is_legacy_match:
        raise StudentPlanMismatchError(
            f"Student {payload.student_id} is not assigned to learning plan "
            f"{payload.learning_plan_id}."
        )

    content = db.execute(
        select(LearningContent).where(
            LearningContent.id == payload.learning_content_id,
            LearningContent.learning_plan_id == payload.learning_plan_id,
        )
    ).scalar_one_or_none()

    if content is None or not content.is_active:
        raise LearningContentNotAvailableError(
            f"Learning content {payload.learning_content_id} is not "
            f"available for learning plan {payload.learning_plan_id}."
        )

    # Student existence/ownership is already implied by the
    # assignment/legacy check above and _get_owned_plan's teacher
    # check, so a separate Student ownership lookup is only needed
    # here to read current_difficulty_level for the snapshot.
    student = db.get(Student, payload.student_id)
    assert student is not None  # guaranteed by the assignment/legacy match above

    session = LearningSession(
        student_id=payload.student_id,
        learning_plan_id=payload.learning_plan_id,
        learning_content_id=payload.learning_content_id,
        started_at=datetime.now(timezone.utc),
        status="started",
        difficulty_level_at_session=student.current_difficulty_level,
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    return session


def list_learning_sessions_for_teacher(
    db: DBSession, teacher_id: int, learning_plan_id: int | None = None
) -> list[LearningSession]:
    """
    List all learning sessions owned by the given teacher (across all
    their plans), optionally filtered to a single plan.

    Raises LearningPlanNotOwnedByTeacherError if learning_plan_id is
    given but does not exist or belongs to a different teacher.
    """
    query = select(LearningSession).join(LearningPlan).where(
        LearningPlan.teacher_id == teacher_id
    )
    if learning_plan_id is not None:
        _get_owned_plan(db, teacher_id, learning_plan_id)
        query = query.where(LearningSession.learning_plan_id == learning_plan_id)

    result = db.execute(query)
    return list(result.scalars().all())


def get_learning_session_for_teacher(
    db: DBSession, teacher_id: int, session_id: int
) -> LearningSession:
    """
    Get a single session by id, scoped to the requesting teacher via
    its plan's ownership.

    Raises LearningSessionNotFoundError if the session does not exist
    or its plan belongs to a different teacher.
    """
    session = db.execute(
        select(LearningSession)
        .join(LearningPlan)
        .where(
            LearningSession.id == session_id,
            LearningPlan.teacher_id == teacher_id,
        )
    ).scalar_one_or_none()

    if session is None:
        raise LearningSessionNotFoundError(f"Learning session {session_id} not found.")

    return session


def _apply_end_metrics(session: LearningSession, payload: LearningSessionEndRequest) -> None:
    """Apply any optionally-reported metrics from an end-of-session request."""
    if payload.time_spent_seconds is not None:
        session.time_spent_seconds = payload.time_spent_seconds
    if payload.idle_time_seconds is not None:
        session.idle_time_seconds = payload.idle_time_seconds
    if payload.hint_usage_count is not None:
        session.hint_usage_count = payload.hint_usage_count
    if payload.retry_count is not None:
        session.retry_count = payload.retry_count


def complete_learning_session(
    db: DBSession, teacher_id: int, session_id: int, payload: LearningSessionEndRequest
) -> LearningSession:
    """
    Mark a session as completed. Raises InvalidSessionStateError if the
    session is not currently "started" (a completed/abandoned session
    is treated as read-only history, per the frozen model's design
    principle).
    """
    session = get_learning_session_for_teacher(db, teacher_id, session_id)

    if session.status != "started":
        raise InvalidSessionStateError(
            f"Session {session_id} is '{session.status}', not 'started'."
        )

    session.status = "completed"
    session.completed_at = datetime.now(timezone.utc)
    _apply_end_metrics(session, payload)

    db.commit()
    db.refresh(session)
    return session


def abandon_learning_session(
    db: DBSession, teacher_id: int, session_id: int, payload: LearningSessionEndRequest
) -> LearningSession:
    """
    Mark a session as abandoned. Raises InvalidSessionStateError if the
    session is not currently "started".
    """
    session = get_learning_session_for_teacher(db, teacher_id, session_id)

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
