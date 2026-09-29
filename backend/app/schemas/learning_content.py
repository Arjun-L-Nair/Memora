"""
schemas/learning_content.py

Pydantic request/response schemas for teacher-managed Learning Content
(Master Specification Section 6, 10: Learning Content).

Learning Content is created and managed exclusively by the teacher who
owns the parent Learning Plan — students never create or edit content.
Ownership is resolved through LearningPlan.teacher_id (LearningContent
has no direct teacher_id column), enforced in the service layer.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

# Same difficulty-level convention already used for Student.current_difficulty_level.
DifficultyLevel = Literal["Beginner", "Easy", "Medium", "Hard"]


class LearningContentCreate(BaseModel):
    """Request body for POST /learning-content (teacher creates new content)."""

    title: str = Field(..., min_length=1, max_length=150)
    subject: str | None = Field(default=None, max_length=100)
    body: str = Field(..., min_length=1)
    difficulty_level: DifficultyLevel
    learning_plan_id: int
    video_url: str | None = Field(default=None, max_length=500)
    teacher_notes: str | None = Field(default=None)


class LearningContentUpdate(BaseModel):
    """
    Request body for PATCH /learning-content/{id}.

    All fields optional (partial update). learning_plan_id is
    intentionally excluded — reassigning content to a different plan is
    a distinct, more significant operation not required by the
    specification. is_active is excluded as well; deactivation has its
    own dedicated endpoint, mirroring Students/Learning Plans.
    """

    title: str | None = Field(default=None, min_length=1, max_length=150)
    subject: str | None = Field(default=None, max_length=100)
    body: str | None = Field(default=None, min_length=1)
    difficulty_level: DifficultyLevel | None = Field(default=None)
    video_url: str | None = Field(default=None, max_length=500)
    teacher_notes: str | None = Field(default=None)


class LearningContentResponse(BaseModel):
    """Response body for all learning content endpoints."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    subject: str | None
    body: str
    difficulty_level: str
    learning_plan_id: int
    is_active: bool
    video_url: str | None
    teacher_notes: str | None
