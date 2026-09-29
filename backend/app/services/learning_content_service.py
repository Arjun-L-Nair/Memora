"""
services/learning_content_service.py

Business logic for teacher-managed Learning Content (Master
Specification Section 6, 10).

LearningContent has no direct teacher_id column — ownership is always
resolved through its parent LearningPlan (LearningContent.learning_plan_id
-> LearningPlan.teacher_id). A teacher attempting to read/update/
deactivate content whose plan belongs to a different teacher receives
the same LearningContentNotFoundError as if the content did not exist
at all, mirroring the pattern established in student_service.py and
learning_plan_service.py.

Reassignment of content to a different plan is not supported (see
Phase 7 planning verification) — update_learning_content() never
touches learning_plan_id.

Deletion is never performed. Per the frozen soft-delete philosophy,
removing content means deactivating it (is_active=False) — existing
LearningSessions that reference it must persist unaffected.

Phase 15 Module 3 — Adaptive Content Recommendation:
    recommend_learning_content_for_student() closes the second half of
    the neuroadaptive loop: given an authorized learning plan, it picks
    the plan's best-matching ACTIVE content for the plan's student's
    CURRENT difficulty level (Student.current_difficulty_level, kept
    up to date by Phase 15 Module 2). It reuses the exact ownership
    check already used by every other function in this file
    (_get_owned_plan) — never a second, parallel authorization path —
    so a recommendation can never surface content belonging to another
    teacher's plan. It reuses DIFFICULTY_ORDER from
    app.services.difficulty_adjustment_service (Module 1, frozen)
    rather than redefining the Beginner/Easy/Medium/Hard ordering a
    second time. No ML/LLM call is involved: the match is a pure,
    deterministic nearest-difficulty calculation over already-loaded
    rows.
"""

from __future__ import annotations

from typing import NamedTuple

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import LearningContent, LearningPlan, Student
from app.schemas.learning_content import LearningContentCreate, LearningContentUpdate
from app.services.difficulty_adjustment_service import DIFFICULTY_ORDER
from app.services.learning_session_service import StudentPlanMismatchError


class LearningContentNotFoundError(Exception):
    """Raised when content does not exist, or its plan is not owned by the requesting teacher."""


class LearningPlanNotOwnedByTeacherError(Exception):
    """Raised when the target learning plan does not exist or is not owned by the requesting teacher."""


def _get_owned_plan(db: Session, teacher_id: int, plan_id: int) -> LearningPlan:
    """
    Shared check: confirm a learning plan exists and is owned by the
    given teacher. Raises LearningPlanNotOwnedByTeacherError otherwise.
    """
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


def create_learning_content(
    db: Session, teacher_id: int, payload: LearningContentCreate
) -> LearningContent:
    """
    Create new learning content under one of the teacher's own plans.

    Raises LearningPlanNotOwnedByTeacherError if the plan does not
    exist or belongs to a different teacher.
    """
    _get_owned_plan(db, teacher_id, payload.learning_plan_id)

    content = LearningContent(
        title=payload.title,
        subject=payload.subject,
        body=payload.body,
        difficulty_level=payload.difficulty_level,
        learning_plan_id=payload.learning_plan_id,
        video_url=payload.video_url,
        teacher_notes=payload.teacher_notes,
    )
    db.add(content)
    db.commit()
    db.refresh(content)
    return content


def list_learning_content_for_teacher(
    db: Session, teacher_id: int, learning_plan_id: int | None = None
) -> list[LearningContent]:
    """
    List all learning content owned by the given teacher (across all
    their plans), optionally filtered to a single plan.

    Raises LearningPlanNotOwnedByTeacherError if learning_plan_id is
    given but does not exist or belongs to a different teacher.
    """
    query = select(LearningContent).join(LearningPlan).where(
        LearningPlan.teacher_id == teacher_id
    )
    if learning_plan_id is not None:
        _get_owned_plan(db, teacher_id, learning_plan_id)
        query = query.where(LearningContent.learning_plan_id == learning_plan_id)

    result = db.execute(query)
    return list(result.scalars().all())


def get_learning_content_for_teacher(
    db: Session, teacher_id: int, content_id: int
) -> LearningContent:
    """
    Get a single piece of content by id, scoped to the requesting
    teacher via its parent plan's ownership.

    Raises LearningContentNotFoundError if the content does not exist
    or its plan belongs to a different teacher.
    """
    content = db.execute(
        select(LearningContent)
        .join(LearningPlan)
        .where(
            LearningContent.id == content_id,
            LearningPlan.teacher_id == teacher_id,
        )
    ).scalar_one_or_none()

    if content is None:
        raise LearningContentNotFoundError(f"Learning content {content_id} not found.")

    return content


def update_learning_content(
    db: Session, teacher_id: int, content_id: int, payload: LearningContentUpdate
) -> LearningContent:
    """
    Update content's editable fields (title, subject, body,
    difficulty_level). learning_plan_id is never modified here —
    reassignment between plans is not supported.

    Raises LearningContentNotFoundError if the content does not exist
    or its plan belongs to a different teacher.
    """
    content = get_learning_content_for_teacher(db, teacher_id, content_id)

    if payload.title is not None:
        content.title = payload.title
    if payload.subject is not None:
        content.subject = payload.subject
    if payload.body is not None:
        content.body = payload.body
    if payload.difficulty_level is not None:
        content.difficulty_level = payload.difficulty_level
    # video_url and teacher_notes use explicit None check so a teacher
    # can clear them by passing an empty string (which gets stored as-is).
    # Passing the field at all (even as None) updates it; omitting the
    # field entirely leaves it unchanged — standard PATCH semantics.
    if "video_url" in payload.model_fields_set:
        content.video_url = payload.video_url
    if "teacher_notes" in payload.model_fields_set:
        content.teacher_notes = payload.teacher_notes

    db.commit()
    db.refresh(content)
    return content


def deactivate_learning_content(
    db: Session, teacher_id: int, content_id: int
) -> LearningContent:
    """
    Deactivate learning content (soft delete). Existing LearningSessions
    that reference it are preserved and unaffected — only is_active is
    set to False, which blocks NEW session assignments against it (see
    learning_session_service.py).

    Raises LearningContentNotFoundError if the content does not exist
    or its plan belongs to a different teacher.
    """
    content = get_learning_content_for_teacher(db, teacher_id, content_id)
    content.is_active = False
    db.commit()
    db.refresh(content)
    return content


class ContentRecommendationResult(NamedTuple):
    """
    Output of a content recommendation: the picked content (or None if
    no active content is available), plus a human-readable explanation
    of why it was picked — mirroring the explainability pattern already
    used by adaptive_suggestion_rules.SuggestionResult and
    difficulty_adjustment_service.DifficultyAdjustmentResult.
    """

    content: LearningContent | None
    reasoning: str


def _difficulty_distance(current: str, candidate: str) -> int:
    """
    Number of steps between two difficulty levels along the canonical
    Beginner -> Easy -> Medium -> Hard ordering (Module 1's
    DIFFICULTY_ORDER, reused — not redefined). Levels outside that
    fixed set cannot occur here: both values originate from columns
    already constrained to the same four literals
    (Student.current_difficulty_level, LearningContent.difficulty_level).
    """
    return abs(DIFFICULTY_ORDER.index(current) - DIFFICULTY_ORDER.index(candidate))


def recommend_learning_content_for_student(
    db: Session, teacher_id: int, learning_plan_id: int, student_id: int
) -> ContentRecommendationResult:
    """
    Recommend the best-matching ACTIVE learning content, within one of
    the teacher's own learning plans, for the given student's current
    difficulty level.

    student_id is now an explicit parameter (post plan-reuse
    restructure — a plan may be assigned to many students, so "the
    plan's student" is no longer a single well-defined thing; the
    caller must say which assigned student they mean).

    Selection is deterministic:
        1. Only is_active content belonging to this exact plan is
           eligible (mirrors the same availability check already
           enforced in learning_session_service.create_learning_session
           — inactive content is never eligible for a new assignment).
        2. Candidates are ranked by absolute distance from the
           student's current_difficulty_level along DIFFICULTY_ORDER —
           an exact match (distance 0) always wins.
        3. Ties (e.g. Easy and Hard are both one step from Medium) are
           broken by preferring the EASIER of the two candidates first
           (lower DIFFICULTY_ORDER index), consistent with this
           project's calm/low-sensory-overload, avoid-frustration
           design philosophy (Master Specification Section 9) —
           preferring to under- rather than over-challenge on a tie.
        4. Any remaining tie (identical distance AND identical
           difficulty_level) is broken by lowest content id, for full
           determinism.
        5. Beginner/Hard are natural floor/ceiling of DIFFICULTY_ORDER:
           there is nothing "below Beginner" or "above Hard" to select,
           so those boundaries require no special-case logic beyond
           the distance calculation itself.

    Returns a ContentRecommendationResult with content=None (and an
    explanatory reasoning string) if the plan has no active content at
    all — this is a graceful, expected outcome, not an error.

    Raises:
        LearningPlanNotOwnedByTeacherError: the plan does not exist or
            belongs to a different teacher (reused directly from
            _get_owned_plan — never a second, parallel ownership check).
        StudentPlanMismatchError: the given student is not assigned to
            this plan (checked independently here too, not only by the
            caller — see learning_session_service.create_learning_session
            for the identical assigned-or-legacy-match pattern this
            mirrors).
    """
    plan = _get_owned_plan(db, teacher_id, learning_plan_id)

    is_assigned = any(a.student_id == student_id for a in plan.assignments)
    is_legacy_match = plan.student_id is not None and plan.student_id == student_id
    if not is_assigned and not is_legacy_match:
        raise StudentPlanMismatchError(
            f"Student {student_id} is not assigned to learning plan {learning_plan_id}."
        )

    student = db.get(Student, student_id)
    assert student is not None  # guaranteed by the assignment/legacy match above

    candidates = db.execute(
        select(LearningContent).where(
            LearningContent.learning_plan_id == learning_plan_id,
            LearningContent.is_active.is_(True),
        )
    ).scalars().all()

    if not candidates:
        return ContentRecommendationResult(
            content=None,
            reasoning=(
                f"No active learning content exists in plan "
                f"{learning_plan_id} to recommend."
            ),
        )

    current_level = student.current_difficulty_level

    best = min(
        candidates,
        key=lambda c: (
            _difficulty_distance(current_level, c.difficulty_level),
            DIFFICULTY_ORDER.index(c.difficulty_level),
            c.id,
        ),
    )
    distance = _difficulty_distance(current_level, best.difficulty_level)

    if distance == 0:
        reasoning = (
            f"Content '{best.title}' (difficulty='{best.difficulty_level}') "
            f"is an exact match for the student's current difficulty level "
            f"('{current_level}')."
        )
    else:
        reasoning = (
            f"No active content at the student's current difficulty level "
            f"('{current_level}') was available in this plan; "
            f"'{best.title}' (difficulty='{best.difficulty_level}') is the "
            f"nearest available level, {distance} step(s) away."
        )

    return ContentRecommendationResult(content=best, reasoning=reasoning)
