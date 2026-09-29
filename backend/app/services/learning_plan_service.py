"""
services/learning_plan_service.py

Business logic for teacher-managed Learning Plans (Master Specification
Section 6, 10: Learning Plan Management).

Every operation here is scoped to the requesting teacher's own plans. A
teacher attempting to read/update/deactivate a plan belonging to a
different teacher receives the same LearningPlanNotFoundError as if the
plan did not exist at all — this mirrors student_service.py's pattern
and avoids leaking which plans exist under other teachers' accounts.

A plan may only be created for a student owned by the same teacher —
this is enforced explicitly here, since the database foreign key alone
only guarantees the student exists, not that it belongs to the creating
teacher.

Deletion is never performed. Per the frozen soft-delete philosophy
(Phase 2/3 design decisions), removing a plan means deactivating it
(is_active=False) — its LearningContent/LearningSessions must persist.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import LearningPlan, PlanAssignment, Student
from app.schemas.learning_plan import (
    LearningPlanCreate,
    LearningPlanResponse,
    LearningPlanUpdate,
)


class LearningPlanNotFoundError(Exception):
    """Raised when a plan does not exist, or does not belong to the requesting teacher."""


class StudentNotOwnedByTeacherError(Exception):
    """Raised when the target student does not exist or is not owned by the requesting teacher."""


def _get_owned_student(db: Session, teacher_id: int, student_id: int) -> Student:
    """
    Shared check: confirm a student exists and is owned by the given
    teacher. Raises StudentNotOwnedByTeacherError otherwise.
    """
    student = db.execute(
        select(Student).where(
            Student.id == student_id, Student.teacher_id == teacher_id
        )
    ).scalar_one_or_none()

    if student is None:
        raise StudentNotOwnedByTeacherError(
            f"Student {student_id} does not belong to this teacher."
        )

    return student


def to_response(plan: LearningPlan) -> LearningPlanResponse:
    """
    Build the API response for a plan, including assigned_student_ids —
    the one field that can't come straight from model_validate(), since
    it's derived from the assignments relationship rather than a plain
    column. Every endpoint in api/v1/learning_plans.py returns a plan
    through this helper (never a bare LearningPlanResponse.model_validate(plan))
    so that field is never accidentally left empty.
    """
    return LearningPlanResponse(
        id=plan.id,
        title=plan.title,
        description=plan.description,
        student_id=plan.student_id,
        teacher_id=plan.teacher_id,
        estimated_duration_minutes=plan.estimated_duration_minutes,
        is_active=plan.is_active,
        assigned_student_ids=[a.student_id for a in plan.assignments],
    )


def create_learning_plan(
    db: Session, teacher_id: int, payload: LearningPlanCreate
) -> LearningPlan:
    """
    Create a new learning plan owned by the given teacher.

    payload.student_id is optional (legacy one-step convenience) — the
    plan-reuse restructure's normal flow is to create the plan
    unassigned, add content to it, then assign it to any number of
    students via assign_plan_to_students(). If student_id IS provided,
    this still creates exactly one PlanAssignment row immediately, so
    callers/tests written against the old one-student-per-plan flow
    keep working unchanged.

    Raises StudentNotOwnedByTeacherError if student_id is given but
    the student does not exist or belongs to a different teacher.
    """
    if payload.student_id is not None:
        _get_owned_student(db, teacher_id, payload.student_id)

    plan = LearningPlan(
        title=payload.title,
        description=payload.description,
        # Legacy column — see LearningPlan.student_id's own docstring.
        # Setting it here (when provided) keeps old single-student
        # reads of this column working; it is never read for
        # authorization/recommendation purposes anywhere else in the
        # codebase anymore.
        student_id=payload.student_id,
        teacher_id=teacher_id,
        estimated_duration_minutes=payload.estimated_duration_minutes,
    )
    db.add(plan)
    db.flush()  # assign plan.id without a full commit yet

    if payload.student_id is not None:
        db.add(PlanAssignment(learning_plan_id=plan.id, student_id=payload.student_id))

    db.commit()
    db.refresh(plan)
    return plan


def assign_plan_to_students(
    db: Session, teacher_id: int, plan_id: int, student_ids: list[int]
) -> LearningPlan:
    """
    Assign a plan to one or more of the teacher's own students. Silently
    skips any student_id already assigned (idempotent — re-assigning an
    already-assigned student is a no-op, not an error), so a teacher
    can freely re-submit a roster selection without needing to compute
    the diff themselves.

    Raises:
        LearningPlanNotFoundError: plan doesn't exist or isn't owned
            by this teacher.
        StudentNotOwnedByTeacherError: any of the given student_ids
            doesn't exist or belongs to a different teacher — raised
            before any assignment is written, so this is all-or-
            nothing, never a partial assignment.
    """
    plan = get_learning_plan_for_teacher(db, teacher_id, plan_id)

    # Validate every student up front (all-or-nothing), then compute
    # which ones aren't already assigned.
    for student_id in student_ids:
        _get_owned_student(db, teacher_id, student_id)

    already_assigned = {a.student_id for a in plan.assignments}
    for student_id in student_ids:
        if student_id not in already_assigned:
            db.add(PlanAssignment(learning_plan_id=plan.id, student_id=student_id))

    db.commit()
    db.refresh(plan)
    return plan


def unassign_plan_from_student(
    db: Session, teacher_id: int, plan_id: int, student_id: int
) -> LearningPlan:
    """
    Remove one student's assignment to a plan. A no-op (not an error)
    if that student wasn't assigned in the first place — removing
    something already absent is a safe, idempotent operation.

    Raises LearningPlanNotFoundError if the plan doesn't exist or
    isn't owned by this teacher.
    """
    plan = get_learning_plan_for_teacher(db, teacher_id, plan_id)

    assignment = db.execute(
        select(PlanAssignment).where(
            PlanAssignment.learning_plan_id == plan_id,
            PlanAssignment.student_id == student_id,
        )
    ).scalar_one_or_none()

    if assignment is not None:
        db.delete(assignment)
        db.commit()
        db.refresh(plan)

    return plan


def list_learning_plans_for_teacher(db: Session, teacher_id: int) -> list[LearningPlan]:
    """List all learning plans owned by the given teacher (active and inactive)."""
    result = db.execute(
        select(LearningPlan).where(LearningPlan.teacher_id == teacher_id)
    )
    return list(result.scalars().all())


def get_learning_plan_for_teacher(
    db: Session, teacher_id: int, plan_id: int
) -> LearningPlan:
    """
    Get a single learning plan by id, scoped to the requesting teacher.

    Raises LearningPlanNotFoundError if the plan does not exist or is
    owned by a different teacher.
    """
    plan = db.execute(
        select(LearningPlan).where(
            LearningPlan.id == plan_id, LearningPlan.teacher_id == teacher_id
        )
    ).scalar_one_or_none()

    if plan is None:
        raise LearningPlanNotFoundError(f"Learning plan {plan_id} not found.")

    return plan


def update_learning_plan(
    db: Session, teacher_id: int, plan_id: int, payload: LearningPlanUpdate
) -> LearningPlan:
    """
    Update a learning plan's editable fields (title, description,
    estimated_duration_minutes).

    Raises LearningPlanNotFoundError if the plan does not exist or is
    owned by a different teacher.
    """
    plan = get_learning_plan_for_teacher(db, teacher_id, plan_id)

    if payload.title is not None:
        plan.title = payload.title
    if payload.description is not None:
        plan.description = payload.description
    if payload.estimated_duration_minutes is not None:
        plan.estimated_duration_minutes = payload.estimated_duration_minutes

    db.commit()
    db.refresh(plan)
    return plan


def deactivate_learning_plan(
    db: Session, teacher_id: int, plan_id: int
) -> LearningPlan:
    """
    Deactivate a learning plan (soft delete). Its LearningContent and
    LearningSessions are preserved — only is_active is set to False.

    Raises LearningPlanNotFoundError if the plan does not exist or is
    owned by a different teacher.
    """
    plan = get_learning_plan_for_teacher(db, teacher_id, plan_id)
    plan.is_active = False
    db.commit()
    db.refresh(plan)
    return plan
