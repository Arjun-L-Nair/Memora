"""
services/quiz_providers/template_provider.py

Deterministic template quiz provider (Master Specification Section 7).

Provides two tiers of quiz questions:

1. CONTENT-AWARE (preferred): when the quiz_service passes a content_body
   string, this provider extracts key sentences from it and builds
   fill-in-the-gap / "which sentence is correct" questions directly from
   the lesson material the student just read. No AI, no network — pure
   deterministic text processing.

2. GENERIC FALLBACK: when no content_body is available, returns the
   original static question bank keyed by difficulty level. This path
   is only used as a last resort and should become increasingly rare as
   teachers add content bodies to their lessons.

This is the ONLY provider guaranteed to always succeed. It is always
the final fallback in the FallbackQuizProvider chain.
"""

from __future__ import annotations

import re

from app.services.quiz_providers.base import (
    QuizGenerationResult,
    QuizProvider,
    QuizQuestionInternal,
)

# ─── Generic static bank (difficulty-keyed) ───────────────────────────────────
_GENERIC_BANK: dict[str, list[QuizQuestionInternal]] = {
    "Beginner": [
        QuizQuestionInternal(question_id="b1", prompt="What is 2 + 2?",
            options=["2", "3", "4", "5", "6"], correct_option_index=2),
        QuizQuestionInternal(question_id="b2", prompt="Which word means the opposite of 'big'?",
            options=["Large", "Huge", "Small", "Tall", "Wide"], correct_option_index=2),
        QuizQuestionInternal(question_id="b3", prompt="How many days are in a week?",
            options=["4", "5", "6", "7", "8"], correct_option_index=3),
        QuizQuestionInternal(question_id="b4", prompt="What color do you get by mixing blue and yellow?",
            options=["Purple", "Red", "Green", "Orange", "Pink"], correct_option_index=2),
        QuizQuestionInternal(question_id="b5", prompt="Which animal says 'moo'?",
            options=["Dog", "Cat", "Cow", "Duck", "Horse"], correct_option_index=2),
    ],
    "Easy": [
        QuizQuestionInternal(question_id="e1", prompt="What is 5 + 7?",
            options=["10", "11", "12", "13", "14"], correct_option_index=2),
        QuizQuestionInternal(question_id="e2", prompt="What is the capital of France?",
            options=["Berlin", "Madrid", "Rome", "London", "Paris"], correct_option_index=4),
        QuizQuestionInternal(question_id="e3", prompt="How many sides does a triangle have?",
            options=["2", "3", "4", "5", "6"], correct_option_index=1),
        QuizQuestionInternal(question_id="e4", prompt="Which season comes after winter?",
            options=["Summer", "Spring", "Autumn", "Fall", "Rainy"], correct_option_index=1),
        QuizQuestionInternal(question_id="e5", prompt="What do bees make?",
            options=["Honey", "Milk", "Silk", "Butter", "Syrup"], correct_option_index=0),
    ],
    "Medium": [
        QuizQuestionInternal(question_id="m1", prompt="What is 12 × 8?",
            options=["84", "86", "94", "96", "104"], correct_option_index=3),
        QuizQuestionInternal(question_id="m2", prompt="What gas do plants absorb during photosynthesis?",
            options=["Oxygen", "Carbon dioxide", "Nitrogen", "Hydrogen", "Helium"], correct_option_index=1),
        QuizQuestionInternal(question_id="m3", prompt="Which planet is closest to the Sun?",
            options=["Venus", "Earth", "Mars", "Mercury", "Jupiter"], correct_option_index=3),
        QuizQuestionInternal(question_id="m4", prompt="What is the largest ocean on Earth?",
            options=["Atlantic", "Arctic", "Indian", "Southern", "Pacific"], correct_option_index=4),
        QuizQuestionInternal(question_id="m5", prompt="How many continents are there?",
            options=["5", "6", "7", "8", "9"], correct_option_index=2),
    ],
    "Hard": [
        QuizQuestionInternal(question_id="h1", prompt="What is the square root of 144?",
            options=["10", "11", "12", "13", "14"], correct_option_index=2),
        QuizQuestionInternal(question_id="h2",
            prompt="In which year did the First World War begin?",
            options=["1910", "1912", "1914", "1916", "1918"], correct_option_index=2),
        QuizQuestionInternal(question_id="h3",
            prompt="What is the chemical symbol for Gold?",
            options=["Ag", "Go", "Gd", "Au", "Gl"], correct_option_index=3),
        QuizQuestionInternal(question_id="h4",
            prompt="Who developed the theory of general relativity?",
            options=["Isaac Newton", "Niels Bohr", "Albert Einstein", "Galileo Galilei", "Max Planck"], correct_option_index=2),
        QuizQuestionInternal(question_id="h5",
            prompt="What is the powerhouse of the cell called?",
            options=["Nucleus", "Ribosome", "Golgi Body", "Mitochondria", "Cytoplasm"], correct_option_index=3),
    ],
}

# ─── Content-aware question builder ───────────────────────────────────────────

def _clean_sentences(text: str) -> list[str]:
    """
    Split text into clean sentences, filtering out very short fragments
    and lines that look like headings or single-word entries.
    """
    # Split on sentence-ending punctuation or newlines
    raw = re.split(r"(?<=[.!?])\s+|\n+", text.strip())
    sentences = []
    for s in raw:
        s = s.strip()
        # Keep sentences that have at least 6 words and aren't a heading
        words = s.split()
        if len(words) >= 6 and not s.endswith(":"):
            sentences.append(s)
    return sentences


def _build_content_questions(
    body: str,
    difficulty_level: str,
    n: int = 5,
) -> list[QuizQuestionInternal]:
    """
    Build up to `n` questions directly from the content body.

    Strategy (fully deterministic, no randomness):
      1. Extract the first `n` qualifying sentences from the body.
      2. For each sentence, blank out the longest meaningful word
         (≥5 chars, not a stop word) to create a fill-in-the-gap prompt.
      3. Generate two plausible-looking distractors by picking other
         long words from the same body text.
      4. If fewer than `n` sentences qualify, fill the remainder with
         generic questions for the given difficulty level.
    """
    STOP = {
        "about", "after", "also", "among", "around", "because", "before",
        "between", "during", "every", "first", "from", "have", "into",
        "large", "learn", "like", "make", "many", "more", "most", "much",
        "often", "other", "over", "people", "place", "said", "same",
        "since", "some", "still", "such", "than", "that", "their", "them",
        "then", "there", "these", "they", "this", "those", "through",
        "time", "under", "upon", "used", "very", "want", "well", "were",
        "what", "when", "where", "which", "while", "will", "with", "would",
        "your",
    }

    # Collect all long, non-stop words from the full body for distractors
    all_words = [
        w.strip(".,;:!?\"'()[]") for w in body.split()
        if len(w.strip(".,;:!?\"'()[]")) >= 5
        and w.strip(".,;:!?\"'()[]").lower() not in STOP
        and w.strip(".,;:!?\"'()[]").isalpha()
    ]
    # Deduplicate while preserving order
    seen: set[str] = set()
    unique_words: list[str] = []
    for w in all_words:
        if w.lower() not in seen:
            seen.add(w.lower())
            unique_words.append(w)

    sentences = _clean_sentences(body)
    questions: list[QuizQuestionInternal] = []

    for i, sentence in enumerate(sentences[:n]):
        words_in_sentence = sentence.split()
        # Find the best word to blank: longest qualifying word
        candidate = max(
            (w.strip(".,;:!?\"'()[]") for w in words_in_sentence
             if len(w.strip(".,;:!?\"'()[]")) >= 5
             and w.strip(".,;:!?\"'()[]").lower() not in STOP
             and w.strip(".,;:!?\"'()[]").isalpha()),
            key=len,
            default="",
        )
        if not candidate:
            continue

        prompt = f'Fill in the blank: "{sentence.replace(candidate, "_____")}"'

        # Distractors: other unique words from the body, different from
        # answer. 4 distractors + 1 correct answer = 5 total options.
        distractors = [
            w for w in unique_words
            if w.lower() != candidate.lower()
        ][:4]

        if len(distractors) < 4:
            # Not enough distinct qualifying words in the body to reach
            # 5 total options — fall back to generic for this slot
            # rather than shipping a question with fewer options than
            # the rest of the quiz.
            continue

        # Answer is always at index 0; options are shuffled deterministically
        # by difficulty level offset so different levels get different orders
        offset = ["Beginner", "Easy", "Medium", "Hard"].index(
            difficulty_level if difficulty_level in ["Beginner", "Easy", "Medium", "Hard"]
            else "Easy"
        )
        options = [candidate] + distractors
        # Rotate options by offset for variety without randomness
        correct_index = 0
        rotated = options[offset % len(options):] + options[:offset % len(options)]
        correct_index = rotated.index(candidate)

        questions.append(QuizQuestionInternal(
            question_id=f"ca_{i+1}",
            prompt=prompt,
            options=rotated,
            correct_option_index=correct_index,
        ))

    return questions


# ─── Provider ─────────────────────────────────────────────────────────────────

class TemplateQuizProvider(QuizProvider):
    """
    Always-succeeding quiz provider. Prefers content-aware questions
    when content_body is supplied; falls back to the static generic
    bank when it is not (or when the body yields fewer than n questions).
    """

    def generate_quiz(
        self,
        difficulty_level: str,
        content_body: str | None = None,
    ) -> QuizGenerationResult:
        questions: list[QuizQuestionInternal] = []

        if content_body:
            questions = _build_content_questions(content_body, difficulty_level, n=5)

        # Top up with generic questions if content didn't yield enough
        if len(questions) < 5:
            generic = _GENERIC_BANK.get(
                difficulty_level,
                _GENERIC_BANK["Easy"],
            )
            needed = 5 - len(questions)
            questions += generic[:needed]

        return QuizGenerationResult(questions=questions, source="template_fallback")
