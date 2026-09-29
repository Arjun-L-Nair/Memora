"""
schemas/student.py

Pydantic request/response schemas for teacher-managed Student accounts
(Master Specification Section 4, 6: Student Management).

Students never self-register — a teacher creates and manages every
Student account. The PIN is write-only: it is accepted on create and on
the dedicated reset endpoint, but never present in any response schema
(StudentResponse deliberately excludes pin_hash/pin).
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class StudentCreate(BaseModel):
    """Request body for POST /students (teacher creates a new student)."""

    student_code: str = Field(..., min_length=1, max_length=20)
    full_name: str = Field(..., min_length=1, max_length=100)
    pin: str = Field(
        ...,
        pattern=r"^\d{4}$",
        description="Exactly 4 numeric digits.",
    )


class StudentUpdate(BaseModel):
    """
    Request body for PATCH /students/{id}.

    All fields optional (partial update). PIN is intentionally excluded
    here — changing a PIN is a distinct, more sensitive action handled
    by its own endpoint (POST /students/{id}/reset-pin), not folded into
    general profile edits.
    """

    full_name: str | None = Field(default=None, min_length=1, max_length=100)
    student_code: str | None = Field(default=None, min_length=1, max_length=20)


class StudentPinResetRequest(BaseModel):
    """Request body for POST /students/{id}/reset-pin."""

    pin: str = Field(
        ...,
        pattern=r"^\d{4}$",
        description="Exactly 4 numeric digits.",
    )


class StudentResponse(BaseModel):
    """
    Response body for all student endpoints. Never includes pin_hash —
    PIN is write-only and never returned.
    """

    model_config = ConfigDict(from_attributes=True)

    id: int
    student_code: str
    full_name: str
    teacher_id: int
    current_difficulty_level: str
    is_active: bool
