"""
schemas/skill.py

Pydantic request/response schemas for the predefined skills library.
"""

from __future__ import annotations

from pydantic import BaseModel


class SkillSummaryResponse(BaseModel):
    """One skill's status for the student-facing skill list."""

    id: int
    name: str
    description: str
    tier: str
    category: str
    unlocked: bool
    passed: bool


class SkillExerciseResponse(BaseModel):
    """One exercise's question, WITHOUT the answer key — same pattern as QuizQuestionOut."""

    id: int
    prompt: str
    options: list[str]


class SkillExercisesResponse(BaseModel):
    skill_id: int
    skill_name: str
    exercises: list[SkillExerciseResponse]


class SkillAttemptSubmitRequest(BaseModel):
    skill_exercise_id: int
    selected_option_index: int


class SkillAttemptResultResponse(BaseModel):
    """Result of one graded attempt — correctness only, not the answer key text
    (mirrors quiz grading's "you find out if you were right, not the full key")."""

    is_correct: bool
    correct_option_index: int
    skill_passed: bool  # true if THIS attempt completed the skill (all exercises now correct)


class TeacherSkillProgressEntry(BaseModel):
    """One skill's pass/not-passed status, for the teacher-facing progress view."""

    id: int
    name: str
    tier: str
    passed: bool


class TeacherSkillProgressResponse(BaseModel):
    student_id: int
    skills: list[TeacherSkillProgressEntry]
