"""
services/sensory_profile_service.py

Business logic for SensoryProfile (Memora overhaul, Component 3).

Student-owned resource, same pattern as learning_companion_service.py:
the authenticated student's own id is the only identity used, no
ownership chain to guard beyond "this student".

Get-or-create semantics: a student's SensoryProfile is created lazily
with the model's documented defaults the first time it's requested or
updated, rather than requiring a separate explicit "create" step. This
mirrors how a brand-new student has sensible sensory defaults before
ever visiting a settings page.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session as DBSession

from app.models import SensoryProfile, Student
from app.services.student_service import StudentNotFoundError

__all__ = [
    "StudentNotFoundError",
    "get_or_create_sensory_profile",
    "update_sensory_profile",
]


def _get_student(db: DBSession, student_id: int) -> Student:
    student = db.execute(select(Student).where(Student.id == student_id)).scalar_one_or_none()
    if student is None:
        raise StudentNotFoundError(f"Student {student_id} not found.")
    return student


def get_or_create_sensory_profile(db: DBSession, student_id: int) -> SensoryProfile:
    """
    Return the student's SensoryProfile, creating one with model
    defaults if it doesn't exist yet.
    """
    _get_student(db, student_id)  # existence check

    profile = db.execute(
        select(SensoryProfile).where(SensoryProfile.student_id == student_id)
    ).scalar_one_or_none()

    if profile is None:
        profile = SensoryProfile(student_id=student_id)
        db.add(profile)
        db.commit()
        db.refresh(profile)

    return profile


def update_sensory_profile(
    db: DBSession,
    student_id: int,
    *,
    preferred_mode: str | None = None,
    sensory_sensitivity_score: float | None = None,
    reduce_motion: bool | None = None,
    high_contrast: bool | None = None,
    mute_sounds: bool | None = None,
    font_preference: str | None = None,
    attention_span_minutes: int | None = None,
) -> SensoryProfile:
    """
    Update whichever fields are provided (non-None) on the student's
    SensoryProfile, creating it first with defaults if it doesn't
    exist yet. Fields left as None are unchanged - this is a partial
    update (PATCH semantics), not a full replace.
    """
    profile = get_or_create_sensory_profile(db, student_id)

    if preferred_mode is not None:
        profile.preferred_mode = preferred_mode
    if sensory_sensitivity_score is not None:
        profile.sensory_sensitivity_score = sensory_sensitivity_score
    if reduce_motion is not None:
        profile.reduce_motion = reduce_motion
    if high_contrast is not None:
        profile.high_contrast = high_contrast
    if mute_sounds is not None:
        profile.mute_sounds = mute_sounds
    if font_preference is not None:
        profile.font_preference = font_preference
    if attention_span_minutes is not None:
        profile.attention_span_minutes = attention_span_minutes

    db.add(profile)
    db.commit()
    db.refresh(profile)
    return profile
