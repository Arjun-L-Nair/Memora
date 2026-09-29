"""
models/__init__.py

Central import point for all SQLAlchemy ORM models.

Importing every model here — in dependency order — ensures that
SQLAlchemy's mapper registry has all classes available when it resolves
the string-based `relationship()` references (e.g. "Student",
"LearningPlan") declared throughout the individual model files.

This module is also what Alembic's `env.py` should import so that
`Base.metadata` reflects the complete schema for autogenerate migrations.

Usage elsewhere in the app:
    from app.models import Teacher, Student, LearningPlan, ...
"""

from app.database.base import Base

# Import order follows the dependency chain established during design:
# Admin and Teacher have no dependencies on other domain models; each
# subsequent import depends on models imported before it.
from app.models.admin import Admin
from app.models.teacher import Teacher
from app.models.student import Student
from app.models.learning_plan import LearningPlan
from app.models.plan_assignment import PlanAssignment
from app.models.learning_content import LearningContent
from app.models.learning_session import LearningSession
from app.models.quiz_attempt import QuizAttempt
from app.models.engagement_prediction import EngagementPrediction
from app.models.learning_reflection import LearningReflection
from app.models.sensory_profile import SensoryProfile
from app.models.conversation_history import ConversationHistory
from app.models.emotion_log import EmotionLog
from app.models.learning_pattern import LearningPattern
from app.models.skill import Skill
from app.models.skill_exercise import SkillExercise
from app.models.skill_attempt import SkillAttempt

__all__ = [
    "Base",
    "Admin",
    "Teacher",
    "Student",
    "LearningPlan",
    "PlanAssignment",
    "LearningContent",
    "LearningSession",
    "QuizAttempt",
    "EngagementPrediction",
    "LearningReflection",
    "SensoryProfile",
    "ConversationHistory",
    "EmotionLog",
    "LearningPattern",
    "Skill",
    "SkillExercise",
    "SkillAttempt",
]
