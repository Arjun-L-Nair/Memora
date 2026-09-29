"""
services/reflection_providers/template_provider.py

Deterministic, predefined-template reflection provider (Master
Specification Section 7: automatic fallback when Ollama is
unavailable).

Mirrors app.services.quiz_providers.template_provider.TemplateQuizProvider:
requires no external service, no network call, and always succeeds —
the reliability guarantee Section 7 requires. Rules are simple,
deterministic string selection based on the given context; no
randomness.
"""

from __future__ import annotations

from app.services.reflection_providers.base import (
    ReflectionContext,
    ReflectionGenerationResult,
    ReflectionProvider,
)


class TemplateReflectionProvider(ReflectionProvider):
    """Predefined-template reflection provider. Always succeeds."""

    def generate_reflection(self, context: ReflectionContext) -> ReflectionGenerationResult:
        """
        Return a short, encouraging, student-facing reflection based on
        the session's quiz score (if available) and engagement label
        (if available). Deterministic — the same context always
        produces the same text.
        """
        if context.quiz_score is not None:
            if context.quiz_score >= 80:
                text = (
                    f"Great work on this {context.difficulty_level.lower()} "
                    f"lesson! You showed strong understanding of the "
                    f"material — keep up the excellent effort."
                )
            elif context.quiz_score >= 50:
                text = (
                    f"Good effort on this {context.difficulty_level.lower()} "
                    f"lesson. You're making solid progress — a little more "
                    f"practice will help strengthen these skills further."
                )
            else:
                text = (
                    f"You worked through a challenging {context.difficulty_level.lower()} "
                    f"lesson today. It's okay if some parts felt difficult — "
                    f"reviewing this material again will help it click."
                )
        elif context.engagement_label == "Low":
            text = (
                "Thanks for completing this lesson. If anything felt "
                "confusing or hard to focus on, it's worth revisiting "
                "with a bit more time next session."
            )
        else:
            text = (
                f"You completed this {context.difficulty_level.lower()} lesson. "
                f"Nice work staying engaged with the material — keep it going!"
            )

        return ReflectionGenerationResult(content=text, generated_by="template")
