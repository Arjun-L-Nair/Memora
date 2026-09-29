"""
api/v1/skills.py

Predefined skills library router — student practice endpoints and a
teacher-facing progress view. See services/skill_service.py for the
unlock/pass logic this router is a thin wrapper around.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_student, get_current_teacher
from app.database import get_db
from app.models import Student, Teacher
from app.schemas.skill import (
    SkillAttemptResultResponse,
    SkillAttemptSubmitRequest,
    SkillExerciseResponse,
    SkillExercisesResponse,
    SkillSummaryResponse,
    TeacherSkillProgressEntry,
    TeacherSkillProgressResponse,
)
from app.services.skill_service import (
    SkillExerciseNotFoundError,
    SkillLockedError,
    SkillNotFoundError,
    StudentNotOwnedByTeacherError,
    decode_options,
    get_skill_exercises_for_student,
    get_skill_progress_for_student,
    list_skills_with_status,
    submit_skill_attempt,
)

router = APIRouter(prefix="/skills", tags=["Skills"])

_SKILL_NOT_FOUND = HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Skill not found.")
_SKILL_LOCKED = HTTPException(
    status_code=status.HTTP_403_FORBIDDEN,
    detail="This skill is locked — complete the previous tier first.",
)
_EXERCISE_NOT_FOUND = HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Skill exercise not found.")
_STUDENT_NOT_FOUND = HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Student not found.")


@router.get("", response_model=list[SkillSummaryResponse])
def list_skills_endpoint(
    student: Student = Depends(get_current_student),
    db: Session = Depends(get_db),
) -> list[SkillSummaryResponse]:
    """Every skill in the library, in tier order, with the authenticated student's unlock/pass status."""
    summaries = list_skills_with_status(db, student.id)
    return [
        SkillSummaryResponse(
            id=s.skill.id,
            name=s.skill.name,
            description=s.skill.description,
            tier=s.skill.tier,
            category=s.skill.category,
            unlocked=s.unlocked,
            passed=s.passed,
        )
        for s in summaries
    ]


@router.get("/{skill_id}/exercises", response_model=SkillExercisesResponse)
def get_skill_exercises_endpoint(
    skill_id: int,
    student: Student = Depends(get_current_student),
    db: Session = Depends(get_db),
) -> SkillExercisesResponse:
    """The exercises for one skill — only if it's currently unlocked for the authenticated student."""
    try:
        exercises = get_skill_exercises_for_student(db, student.id, skill_id)
    except SkillNotFoundError:
        raise _SKILL_NOT_FOUND
    except SkillLockedError:
        raise _SKILL_LOCKED

    skill_name = exercises[0].skill.name if exercises else ""
    return SkillExercisesResponse(
        skill_id=skill_id,
        skill_name=skill_name,
        exercises=[
            SkillExerciseResponse(id=e.id, prompt=e.prompt, options=decode_options(e.options_json))
            for e in exercises
        ],
    )


@router.post("/{skill_id}/attempts", response_model=SkillAttemptResultResponse)
def submit_skill_attempt_endpoint(
    skill_id: int,
    payload: SkillAttemptSubmitRequest,
    student: Student = Depends(get_current_student),
    db: Session = Depends(get_db),
) -> SkillAttemptResultResponse:
    """Submit one answer to one skill exercise; graded immediately (a fixed answer key, not AI-graded)."""
    try:
        attempt = submit_skill_attempt(
            db, student.id, skill_id, payload.skill_exercise_id, payload.selected_option_index
        )
    except SkillNotFoundError:
        raise _SKILL_NOT_FOUND
    except SkillLockedError:
        raise _SKILL_LOCKED
    except SkillExerciseNotFoundError:
        raise _EXERCISE_NOT_FOUND

    # Re-check pass status after this attempt so the response can tell
    # the student "you just completed this skill!" in the same call,
    # rather than needing a second round-trip.
    summaries = list_skills_with_status(db, student.id)
    skill_passed = any(s.skill.id == skill_id and s.passed for s in summaries)

    return SkillAttemptResultResponse(
        is_correct=attempt.is_correct,
        correct_option_index=attempt.selected_option_index if attempt.is_correct else _correct_index(db, payload.skill_exercise_id),
        skill_passed=skill_passed,
    )


def _correct_index(db: Session, skill_exercise_id: int) -> int:
    """Small helper: look up the correct answer for the response when the student got it wrong."""
    from app.models import SkillExercise

    exercise = db.get(SkillExercise, skill_exercise_id)
    return exercise.correct_option_index if exercise else -1


@router.get("/progress/{student_id}", response_model=TeacherSkillProgressResponse)
def get_skill_progress_endpoint(
    student_id: int,
    teacher: Teacher = Depends(get_current_teacher),
    db: Session = Depends(get_db),
) -> TeacherSkillProgressResponse:
    """Full skill pass/not-passed status for one of the teacher's own students."""
    try:
        entries = get_skill_progress_for_student(db, teacher.id, student_id)
    except StudentNotOwnedByTeacherError:
        raise _STUDENT_NOT_FOUND

    return TeacherSkillProgressResponse(
        student_id=student_id,
        skills=[
            TeacherSkillProgressEntry(id=e.skill.id, name=e.skill.name, tier=e.skill.tier, passed=e.passed)
            for e in entries
        ],
    )
