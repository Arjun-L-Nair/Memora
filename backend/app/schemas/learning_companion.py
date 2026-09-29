"""
schemas/learning_companion.py

Pydantic request/response schemas for Mira, the student learning
companion (Memora overhaul, Component 2).
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class CompanionMessageRequest(BaseModel):
    """
    Request body for POST /learning-companion/message. student_message
    is optional - a student may request a check-in from Mira without
    saying anything specific. interaction_mode selects an
    autism-specific response style.
    """

    student_message: str | None = Field(default=None, max_length=500)
    interaction_mode: Literal["chat", "social_story", "visual_schedule", "calm_down"] = "chat"


class CompanionMessageResponse(BaseModel):
    """Response body containing Mira's generated message, its source, and any detected emotion."""

    message: str
    generated_by: Literal["gemini", "ollama", "template"]
    detected_emotion: str | None = None


class ConversationTurn(BaseModel):
    """One turn in the persisted chat transcript."""

    role: Literal["student", "mira"]
    message: str
    emotion_detected: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class ConversationHistoryResponse(BaseModel):
    turns: list[ConversationTurn]
