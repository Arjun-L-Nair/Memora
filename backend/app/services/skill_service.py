"""
services/skill_service.py

Business logic for the predefined skills library (Easy/Medium/Hard
tiers, tier-gated unlocking). See models/skill.py's module docstring
for the overall architecture; this module is where "is this skill
unlocked for this student" and "has this student passed this skill"
are actually computed.

Unlock rule (the one specified by the project owner):
    - Every Easy-tier skill is always unlocked.
    - A Medium-tier skill unlocks only once the student has PASSED
      every Easy-tier skill.
    - A Hard-tier skill unlocks only once the student has PASSED
      every Medium-tier skill.

"Passed a skill" means: for every SkillExercise belonging to that
skill, the student has at least one correct SkillAttempt (not
necessarily all in the same sitting — attempts accumulate over time,
consistent with a low-pressure, retry-friendly design for autistic
learners rather than an all-or-nothing single attempt).
"""

from __future__ import annotations

import json

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Skill, SkillAttempt, SkillExercise, Student

_TIER_ORDER = ["Easy", "Medium", "Hard"]


class SkillNotFoundError(Exception):
    """Raised when a skill_id doesn't exist."""


class SkillLockedError(Exception):
    """Raised when a student tries to practice a skill that isn't unlocked for them yet."""


class SkillExerciseNotFoundError(Exception):
    """Raised when an exercise_id doesn't exist, or doesn't belong to the given skill."""


class StudentNotOwnedByTeacherError(Exception):
    """Raised when the target student does not exist or is not owned by the requesting teacher."""


def _passed_skill_ids(db: Session, student_id: int, tier: str) -> set[int]:
    """
    Which skill ids in the given tier this student has PASSED (every
    exercise in that skill has at least one correct attempt from this
    student). Computed fresh from SkillAttempt rows every call — see
    models/skill_attempt.py's docstring for why there's no separate
    stored "completed" flag to keep in sync.
    """
    skills = db.execute(select(Skill).where(Skill.tier == tier)).scalars().all()

    correct_exercise_ids = set(
        db.execute(
            select(SkillAttempt.skill_exercise_id).where(
                SkillAttempt.student_id == student_id,
                SkillAttempt.is_correct.is_(True),
            )
        )
        .scalars()
        .all()
    )

    passed: set[int] = set()
    for skill in skills:
        exercise_ids = {ex.id for ex in skill.exercises}
        if exercise_ids and exercise_ids.issubset(correct_exercise_ids):
            passed.add(skill.id)
    return passed


def _tier_unlocked(db: Session, student_id: int, tier: str) -> bool:
    """Easy is always unlocked; Medium/Hard require every skill in the previous tier to be passed."""
    tier_index = _TIER_ORDER.index(tier)
    if tier_index == 0:
        return True

    previous_tier = _TIER_ORDER[tier_index - 1]
    previous_skills = db.execute(select(Skill.id).where(Skill.tier == previous_tier)).scalars().all()
    if not previous_skills:
        return True  # no prior-tier skills defined -> nothing to gate on

    passed = _passed_skill_ids(db, student_id, previous_tier)
    return set(previous_skills).issubset(passed)


class SkillSummary:
    """Plain data holder for one skill's status — used to build the API response."""

    def __init__(self, skill: Skill, unlocked: bool, passed: bool):
        self.skill = skill
        self.unlocked = unlocked
        self.passed = passed


def list_skills_with_status(db: Session, student_id: int) -> list[SkillSummary]:
    """
    Every skill in the library, in tier order (Easy, Medium, Hard) then
    order_index within a tier, each annotated with whether it's
    currently unlocked and whether this student has passed it.
    """
    results: list[SkillSummary] = []
    for tier in _TIER_ORDER:
        tier_unlocked = _tier_unlocked(db, student_id, tier)
        passed_ids = _passed_skill_ids(db, student_id, tier)
        skills = (
            db.execute(select(Skill).where(Skill.tier == tier).order_by(Skill.order_index))
            .scalars()
            .all()
        )
        for skill in skills:
            results.append(SkillSummary(skill=skill, unlocked=tier_unlocked, passed=skill.id in passed_ids))
    return results


def get_skill_exercises_for_student(db: Session, student_id: int, skill_id: int) -> list[SkillExercise]:
    """
    The exercises for one skill, ONLY if that skill is currently
    unlocked for this student.

    Raises:
        SkillNotFoundError: skill_id doesn't exist.
        SkillLockedError: this skill's tier isn't unlocked for this
            student yet.
    """
    skill = db.get(Skill, skill_id)
    if skill is None:
        raise SkillNotFoundError(f"Skill {skill_id} not found.")

    if not _tier_unlocked(db, student_id, skill.tier):
        raise SkillLockedError(f"Skill {skill_id} is not unlocked for this student yet.")

    return sorted(skill.exercises, key=lambda e: e.order_index)


def submit_skill_attempt(
    db: Session,
    student_id: int,
    skill_id: int,
    skill_exercise_id: int,
    selected_option_index: int,
) -> SkillAttempt:
    """
    Record one attempt at one skill exercise and grade it immediately
    (correctness is deterministic — a fixed answer key, unlike an
    AI-graded quiz). The skill must be currently unlocked for this
    student, same gate as get_skill_exercises_for_student.

    Raises:
        SkillNotFoundError: skill_id doesn't exist.
        SkillLockedError: this skill isn't unlocked for this student yet.
        SkillExerciseNotFoundError: skill_exercise_id doesn't exist,
            or doesn't belong to skill_id.
    """
    skill = db.get(Skill, skill_id)
    if skill is None:
        raise SkillNotFoundError(f"Skill {skill_id} not found.")

    if not _tier_unlocked(db, student_id, skill.tier):
        raise SkillLockedError(f"Skill {skill_id} is not unlocked for this student yet.")

    exercise = db.get(SkillExercise, skill_exercise_id)
    if exercise is None or exercise.skill_id != skill_id:
        raise SkillExerciseNotFoundError(
            f"Skill exercise {skill_exercise_id} not found for skill {skill_id}."
        )

    is_correct = selected_option_index == exercise.correct_option_index

    attempt = SkillAttempt(
        student_id=student_id,
        skill_id=skill_id,
        skill_exercise_id=skill_exercise_id,
        selected_option_index=selected_option_index,
        is_correct=is_correct,
    )
    db.add(attempt)
    db.commit()
    db.refresh(attempt)
    return attempt


class TeacherSkillProgressEntry:
    """Plain data holder for one skill's progress, as seen by a teacher viewing a student's summary."""

    def __init__(self, skill: Skill, passed: bool):
        self.skill = skill
        self.passed = passed


def get_skill_progress_for_student(db: Session, teacher_id: int, student_id: int) -> list[TeacherSkillProgressEntry]:
    """
    Full pass/not-passed status for every skill in the library, for
    the teacher-facing progress view. Unlike list_skills_with_status,
    this has no concept of "locked" — a teacher can see full status
    across every tier regardless of what the student has unlocked, so
    she can see exactly how far a student has progressed.

    Raises StudentNotOwnedByTeacherError if the student doesn't exist
    or belongs to a different teacher — a teacher may only view skill
    progress for her own students.
    """
    student = db.execute(
        select(Student).where(Student.id == student_id, Student.teacher_id == teacher_id)
    ).scalar_one_or_none()
    if student is None:
        raise StudentNotOwnedByTeacherError(f"Student {student_id} does not belong to this teacher.")

    results: list[TeacherSkillProgressEntry] = []
    for tier in _TIER_ORDER:
        passed_ids = _passed_skill_ids(db, student_id, tier)
        skills = (
            db.execute(select(Skill).where(Skill.tier == tier).order_by(Skill.order_index))
            .scalars()
            .all()
        )
        for skill in skills:
            results.append(TeacherSkillProgressEntry(skill=skill, passed=skill.id in passed_ids))
    return results


def decode_options(options_json: str) -> list[str]:
    """Shared helper: SkillExercise.options_json (str) -> list[str], used by the API/schema layer."""
    return json.loads(options_json)
