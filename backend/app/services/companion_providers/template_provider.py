"""
services/companion_providers/template_provider.py

Deterministic, predefined-template provider for Mira (Phase 14).
Mirrors app.services.reflection_providers.template_provider exactly:
requires no external service, no network call, always succeeds.
"""

from __future__ import annotations

from app.services.companion_providers.base import (
    CompanionContext,
    CompanionGenerationResult,
    CompanionProvider,
)


class TemplateCompanionProvider(CompanionProvider):
    """Predefined-template companion provider. Always succeeds."""

    def generate_message(self, context: CompanionContext) -> CompanionGenerationResult:
        """
        Return a short, supportive, student-facing message based on the
        student's recent quiz score (if available) and engagement label
        (if available). Deterministic — the same context always
        produces the same message.
        """
        name = context.student_name

        if context.recent_quiz_score is not None:
            if context.recent_quiz_score >= 80:
                text = (
                    f"Hi {name}, I'm Mira! You've been doing great on your "
                    f"quizzes lately — keep up the awesome work!"
                )
            elif context.recent_quiz_score >= 50:
                text = (
                    f"Hi {name}, I'm Mira! You're making good progress. "
                    f"A bit more practice will help things click even more."
                )
            else:
                text = (
                    f"Hi {name}, I'm Mira! Learning can be tricky sometimes, "
                    f"and that's completely okay. Let's keep going one step "
                    f"at a time."
                )
        elif context.recent_engagement_label == "Low":
            text = (
                f"Hi {name}, I'm Mira! If you're feeling distracted or "
                f"unsure, that's alright — take your time, I'm here with you."
            )
        else:
            text = (
                f"Hi {name}, I'm Mira! I'm here to help whenever you need "
                f"support with your learning."
            )

        return CompanionGenerationResult(message=text, generated_by="template")
