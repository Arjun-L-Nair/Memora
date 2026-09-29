"""
schemas/sensory_profile.py

Pydantic request/response schemas for SensoryProfile (Memora overhaul,
Component 3).
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class SensoryProfileResponse(BaseModel):
    student_id: int
    preferred_mode: Literal["visual", "auditory", "text", "mixed"]
    sensory_sensitivity_score: float
    reduce_motion: bool
    high_contrast: bool
    mute_sounds: bool
    font_preference: Literal["default", "opendyslexic"]
    attention_span_minutes: int

    model_config = {"from_attributes": True}


class SensoryProfileUpdateRequest(BaseModel):
    """
    Partial update - every field is optional; only provided fields are
    changed (PATCH semantics), matching
    services.sensory_profile_service.update_sensory_profile().
    """

    preferred_mode: Literal["visual", "auditory", "text", "mixed"] | None = None
    sensory_sensitivity_score: float | None = Field(default=None, ge=0.0, le=1.0)
    reduce_motion: bool | None = None
    high_contrast: bool | None = None
    mute_sounds: bool | None = None
    font_preference: Literal["default", "opendyslexic"] | None = None
    attention_span_minutes: int | None = Field(default=None, ge=1, le=120)
