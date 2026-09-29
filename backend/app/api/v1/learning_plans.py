"""
api/v1/learning_plans.py

Learning Plan management router (Master Specification Section 6, 10).

Every endpoint requires an authenticated Teacher (get_current_teacher,
frozen in Phase 4) - plans are created and managed exclusively by
teachers. This router contains no business logic or database access
itself; it only parses requests, calls
app.services.learning_plan_service, translates service-layer exceptions
into HTTP responses, and returns schemas.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_teacher
from app.database import get_db
from app.models import Teacher
from app.schemas.learning_plan import (
    LearningPlanCreate,
    LearningPlanResponse,
    LearningPlanUpdate,
    PlanAssignRequest,
)
from app.services.learning_plan_service import (
    LearningPlanNotFoundError,
    StudentNotOwnedByTeacherError,
    assign_plan_to_students,
    create_learning_plan,
    deactivate_learning_plan,
    get_learning_plan_for_teacher,
    list_learning_plans_for_teacher,
    to_response,
    unassign_plan_from_student,
    update_learning_plan,
)

router = APIRouter(prefix="/learning-plans", tags=["Learning Plans"])

_PLAN_NOT_FOUND = HTTPException(
    status_code=status.HTTP_404_NOT_FOUND,
    detail="Learning plan not found.",
)

# Same status/reasoning as _PLAN_NOT_FOUND: a teacher should not be able
# to distinguish "that student doesn't exist" from "that student belongs
# to another teacher".
_STUDENT_NOT_OWNED = HTTPException(
    status_code=status.HTTP_404_NOT_FOUND,
    detail="Student not found.",
)


@router.post(
    "", response_model=LearningPlanResponse, status_code=status.HTTP_201_CREATED
)
def create_learning_plan_endpoint(
    payload: LearningPlanCreate,
    teacher: Teacher = Depends(get_current_teacher),
    db: Session = Depends(get_db),
) -> LearningPlanResponse:
    """
    Create a new learning plan for the authenticated teacher. student_id
    is optional now - omit it to create a reusable, unassigned plan and
    assign it to students afterward via POST /{plan_id}/assign.
    """
    try:
        plan = create_learning_plan(db, teacher.id, payload)
    except StudentNotOwnedByTeacherError:
        raise _STUDENT_NOT_OWNED

    return to_response(plan)


@router.get("", response_model=list[LearningPlanResponse])
def list_learning_plans_endpoint(
    teacher: Teacher = Depends(get_current_teacher),
    db: Session = Depends(get_db),
) -> list[LearningPlanResponse]:
    """List all learning plans owned by the authenticated teacher."""
    plans = list_learning_plans_for_teacher(db, teacher.id)
    return [to_response(p) for p in plans]


@router.get("/{plan_id}", response_model=LearningPlanResponse)
def get_learning_plan_endpoint(
    plan_id: int,
    teacher: Teacher = Depends(get_current_teacher),
    db: Session = Depends(get_db),
) -> LearningPlanResponse:
    """Get a single learning plan owned by the authenticated teacher."""
    try:
        plan = get_learning_plan_for_teacher(db, teacher.id, plan_id)
    except LearningPlanNotFoundError:
        raise _PLAN_NOT_FOUND

    return to_response(plan)


@router.patch("/{plan_id}", response_model=LearningPlanResponse)
def update_learning_plan_endpoint(
    plan_id: int,
    payload: LearningPlanUpdate,
    teacher: Teacher = Depends(get_current_teacher),
    db: Session = Depends(get_db),
) -> LearningPlanResponse:
    """Update a learning plan's editable fields."""
    try:
        plan = update_learning_plan(db, teacher.id, plan_id, payload)
    except LearningPlanNotFoundError:
        raise _PLAN_NOT_FOUND

    return to_response(plan)


@router.post("/{plan_id}/deactivate", response_model=LearningPlanResponse)
def deactivate_learning_plan_endpoint(
    plan_id: int,
    teacher: Teacher = Depends(get_current_teacher),
    db: Session = Depends(get_db),
) -> LearningPlanResponse:
    """Deactivate a learning plan (soft delete; its content/sessions are preserved)."""
    try:
        plan = deactivate_learning_plan(db, teacher.id, plan_id)
    except LearningPlanNotFoundError:
        raise _PLAN_NOT_FOUND

    return to_response(plan)


@router.post("/{plan_id}/assign", response_model=LearningPlanResponse)
def assign_plan_endpoint(
    plan_id: int,
    payload: PlanAssignRequest,
    teacher: Teacher = Depends(get_current_teacher),
    db: Session = Depends(get_db),
) -> LearningPlanResponse:
    """
    Assign this plan to one or more of the teacher's own students, from
    her full roster. Already-assigned students are silently skipped
    (idempotent) - safe to re-submit a full roster selection.
    """
    try:
        plan = assign_plan_to_students(db, teacher.id, plan_id, payload.student_ids)
    except LearningPlanNotFoundError:
        raise _PLAN_NOT_FOUND
    except StudentNotOwnedByTeacherError:
        raise _STUDENT_NOT_OWNED

    return to_response(plan)


@router.delete("/{plan_id}/assign/{student_id}", response_model=LearningPlanResponse)
def unassign_plan_endpoint(
    plan_id: int,
    student_id: int,
    teacher: Teacher = Depends(get_current_teacher),
    db: Session = Depends(get_db),
) -> LearningPlanResponse:
    """Remove one student's assignment to this plan (a no-op if they weren't assigned)."""
    try:
        plan = unassign_plan_from_student(db, teacher.id, plan_id, student_id)
    except LearningPlanNotFoundError:
        raise _PLAN_NOT_FOUND

    return to_response(plan)
