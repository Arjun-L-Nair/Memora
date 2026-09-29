"""
schemas/learning_plan.py

Pydantic request/response schemas for teacher-managed Learning Plans
(Master Specification Section 6, 10: Learning Plan Management).

A LearningPlan is created and managed exclusively by the teacher who
owns it — students never create or edit plans. `teacher_id` is never
client-supplied on create; it is always derived from the authenticated
teacher (see api/v1/learning_plans.py), mirroring the pattern already
established for Student Management (Phase 5).
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class LearningPlanCreate(BaseModel):
    """
    Request body for POST /learning-plans (teacher creates a new plan).

    student_id is now OPTIONAL (legacy) — the plan-reuse restructure
    means a plan is created unassigned and then assigned to any number
    of students via POST /learning-plans/{id}/assign, not tied to one
    student at creation time. Passing student_id here still works (it
    immediately creates one PlanAssignment row, for callers/tests that
    prefer the old one-step flow) but is no longer required.
    """

    title: str = Field(..., min_length=1, max_length=150)
    description: str | None = Field(default=None)
    student_id: int | None = Field(default=None)
    estimated_duration_minutes: int | None = Field(default=None, gt=0)


class LearningPlanUpdate(BaseModel):
    """
    Request body for PATCH /learning-plans/{id}.

    All fields optional (partial update). Student assignment is
    intentionally excluded here — see the dedicated
    POST /learning-plans/{id}/assign and DELETE .../assign/{student_id}
    endpoints. is_active is excluded as well; deactivation has its own
    dedicated endpoint, mirroring Student Management's pattern.
    """

    title: str | None = Field(default=None, min_length=1, max_length=150)
    description: str | None = Field(default=None)
    estimated_duration_minutes: int | None = Field(default=None, gt=0)


class LearningPlanResponse(BaseModel):
    """Response body for all learning plan endpoints."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    description: str | None
    student_id: int | None  # legacy — see LearningPlan.student_id's own docstring
    teacher_id: int
    estimated_duration_minutes: int | None
    is_active: bool
    assigned_student_ids: list[int] = Field(default_factory=list)


class PlanAssignRequest(BaseModel):
    """Request body for POST /learning-plans/{id}/assign."""

    student_ids: list[int] = Field(..., min_length=1)


class AssignedStudentSummary(BaseModel):
    """One entry in a plan's assigned-students list — enough for a teacher-facing roster display."""

    model_config = ConfigDict(from_attributes=True)

    student_id: int
    full_name: str
    student_code: str
