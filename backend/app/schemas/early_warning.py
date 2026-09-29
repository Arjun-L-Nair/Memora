"""
schemas/early_warning.py

Pydantic response schemas for the Early-Warning dropout-risk dashboard
(Memora overhaul, Component 4).
"""

from __future__ import annotations

from pydantic import BaseModel


class EarlyWarningResponse(BaseModel):
    student_id: int
    risk_score: float
    risk_level: str
    contributing_factors: list[str]


class AtRiskStudentEntry(BaseModel):
    student_id: int
    student_name: str
    risk_score: float
    risk_level: str
    contributing_factors: list[str]


class AtRiskStudentsResponse(BaseModel):
    students: list[AtRiskStudentEntry]
