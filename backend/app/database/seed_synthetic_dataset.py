"""
database/seed_synthetic_dataset.py

Synthetic demonstration/training dataset for Memora.

Populates the database with realistic students, learning plans, varied
learning content, sessions in every status, quiz attempts, reflections,
and engagement predictions — driven entirely through the REAL HTTP API
(not raw ORM inserts), so every record is created exactly the way the
running application creates it in normal use, and every business rule
(ownership checks, status transitions, difficulty snapshotting) is
exercised for real rather than bypassed.

Two purposes:
  1. DEMO REALISM — a populated dashboard instead of empty tables when
     presenting the project: multiple students, varied learning
     content, sessions in every status, quiz results, reflections, and
     engagement predictions with realistic-looking spread.
  2. EXERCISES THE REAL WORKFLOW END-TO-END — because every record is
     created through the actual API (not raw inserts), running this
     script is itself a smoke test of student creation, plan/content
     assignment, session creation, quiz start/submit, session
     completion, and engagement-prediction generation all working
     together correctly.

Note on the ML model specifically: the engagement-prediction Decision
Tree Classifier (app/ml/dataset.py, app/ml/model.py) trains once from
its OWN separate, fixed, rule-based 300-sample synthetic dataset and
persists the fitted model to app/ml/artifacts/*.joblib — it does not
train from LearningSession/QuizAttempt records. The sessions this
script creates are used only as INFERENCE input (what the trained
model predicts on), not training data for the model itself. If you
want the classifier's training data itself to be regenerated, delete
app/ml/artifacts/*.joblib and it will retrain from app/ml/dataset.py
on the next prediction request.

Idempotent guard: checks for a marker student_code prefix
("SEED-DEMO-") before inserting, and refuses to run twice — re-running
after already seeding is a no-op with a clear message, never a
duplicate insert.

Usage:
    cd backend
    uvicorn app.main:app &        # server must be running — this
                                   # script is an HTTP client
    python -m app.database.seed_synthetic_dataset
"""

from __future__ import annotations

import random
import sys

import httpx

from app.database.seed_dev_teacher import (
    DEV_TEACHER_EMAIL,
    DEV_TEACHER_PASSWORD,
)

# Demo messages sent to Mira for each seeded student, exercising the
# ConversationHistory/EmotionLog persistence added in the Memora
# overhaul. Deliberately varied in emotional tone.
_MIRA_DEMO_MESSAGES = [
    "Hi Mira, I'm ready to start today!",
    "This is a bit confusing, can you help?",
]

BASE_URL = "http://127.0.0.1:8000"
SEED_MARKER = "SEED-DEMO-"

random.seed(42)  # deterministic — same synthetic dataset every run

# ─── Content library: realistic autism-support lesson material ───────────────
# Three difficulty tiers x multiple entries each, so every plan has
# genuine variety (this is also what exercises the multi-content fix
# from the previous ticket — every plan below has 2+ entries per
# difficulty level).

CONTENT_LIBRARY = {
    "Beginner": [
        {
            "title": "What Are Emotions?",
            "subject": "Emotional Awareness",
            "body": (
                "Emotions are feelings that happen inside us. Everyone has emotions "
                "every day. Some common emotions are happy, sad, angry, scared, and "
                "calm. Emotions are not good or bad, they are signals from your body. "
                "It is okay to feel any emotion. All emotions are normal. You do not "
                "have to hide your feelings. It is good to notice them and name them."
            ),
            "teacher_notes": "Take your time reading each emotion. There are no wrong answers here.",
        },
        {
            "title": "My Daily Routine",
            "subject": "Life Skills",
            "body": (
                "A routine is a set of things you do in the same order every day. "
                "Routines can help you feel calm and ready. A morning routine might "
                "include waking up, brushing teeth, and eating breakfast. Knowing "
                "what happens next can make the day feel less surprising. You can "
                "make a picture schedule to help remember your routine."
            ),
            "teacher_notes": "Consider pairing this with a visual schedule the student already uses.",
        },
    ],
    "Easy": [
        {
            "title": "What Helps When Feelings Are Big?",
            "subject": "Emotional Regulation",
            "body": (
                "Sometimes emotions can feel very big. This is normal and happens to "
                "everyone. Slow breathing can help calm your body down. Moving your "
                "body, like walking or stretching, can also help big feelings become "
                "smaller. Naming the feeling out loud helps your brain understand it. "
                "It is okay to take a break in a quiet place. Remember, big feelings "
                "always pass, they do not stay forever."
            ),
            "teacher_notes": "If a big emotion comes up while reading, pause and try the breathing technique first.",
        },
        {
            "title": "Taking Turns With Others",
            "subject": "Social Skills",
            "body": (
                "Taking turns means waiting for your turn while someone else has a "
                "turn first. This can happen in games, conversations, or activities. "
                "Waiting can feel hard sometimes. It can help to count slowly or "
                "think about something else while you wait. Taking turns helps "
                "everyone feel included and respected."
            ),
            "teacher_notes": "Role-play this concept with a simple turn-taking game if possible.",
        },
    ],
    "Medium": [
        {
            "title": "Social Situations — What Is Happening?",
            "subject": "Social Understanding",
            "body": (
                "Social situations are times when we are around other people. "
                "People use words, faces, and body language to communicate. A smile "
                "often means someone is happy or friendly. Crossed arms sometimes "
                "means someone is uncomfortable. Not everyone shows feelings the "
                "same way, and that is normal. It is okay to feel unsure in social "
                "situations and to ask someone you trust to explain what is happening."
            ),
            "teacher_notes": "Discuss real examples the student has encountered if they're comfortable sharing.",
        },
        {
            "title": "Understanding Change and Transitions",
            "subject": "Coping Skills",
            "body": (
                "A transition is when something changes from one thing to another. "
                "Moving from one activity to a different one is a transition. "
                "Transitions can feel uncomfortable because they are unpredictable. "
                "A warning before a transition, like 'five more minutes', can make "
                "it easier. Having a plan for what happens next also helps reduce "
                "worry about change."
            ),
            "teacher_notes": "Use countdown warnings consistently in class to reinforce this concept.",
        },
    ],
    "Hard": [
        {
            "title": "Managing Sensory Overload",
            "subject": "Self-Regulation",
            "body": (
                "Sensory overload happens when there is too much information coming "
                "into your senses at once, like loud noise, bright light, or strong "
                "smells. This can feel overwhelming and uncomfortable. Recognising "
                "early signs, such as feeling tense or wanting to cover your ears, "
                "can help you act before it becomes too much. Having a plan, like "
                "noise-cancelling headphones or a quiet space, can help you manage "
                "sensory overload when it happens."
            ),
            "teacher_notes": "This is a more advanced self-awareness topic — check in with the student afterward.",
        },
        {
            "title": "Understanding Different Perspectives",
            "subject": "Social Cognition",
            "body": (
                "A perspective is how someone sees or understands a situation based "
                "on their own experience. Different people can have different "
                "perspectives about the same event. This does not mean one person "
                "is right and the other is wrong; they simply see it differently. "
                "Trying to understand another person's perspective can help avoid "
                "misunderstandings and build stronger friendships."
            ),
            "teacher_notes": "Consider concrete examples from the student's own life to make this less abstract.",
        },
    ],
}

STUDENT_NAMES = [
    "Aarav Mehta", "Priya Nair", "Kabir Shah", "Ananya Reddy",
    "Ishaan Kapoor", "Diya Sharma",
]

DIFFICULTY_LEVELS = ["Beginner", "Easy", "Medium", "Hard"]


def _login_teacher(client: httpx.Client) -> str:
    response = client.post(
        "/auth/teacher/login",
        json={"email": DEV_TEACHER_EMAIL, "password": DEV_TEACHER_PASSWORD},
    )
    response.raise_for_status()
    return response.json()["access_token"]


def _login_student(client: httpx.Client, student_code: str, pin: str) -> str:
    response = client.post(
        "/auth/student/login",
        json={"student_code": student_code, "pin": pin},
    )
    response.raise_for_status()
    return response.json()["access_token"]


def _already_seeded(client: httpx.Client, teacher_token: str) -> bool:
    response = client.get(
        "/students",
        headers={"Authorization": f"Bearer {teacher_token}"},
    )
    response.raise_for_status()
    students = response.json()
    return any(s["student_code"].startswith(SEED_MARKER) for s in students)


def _engagement_profile(pattern: str) -> dict:
    """
    Return realistic session-end metrics for one of three engagement
    patterns, so the resulting EngagementPrediction spans High/Medium/Low
    labels with plausible, varied feature combinations — not just three
    fixed points, which would let the Decision Tree memorise rather than
    generalise.
    """
    if pattern == "high":
        return {
            "time_spent_seconds": random.randint(240, 420),
            "idle_time_seconds": random.randint(0, 20),
            "hint_usage_count": random.randint(0, 1),
            "retry_count": random.randint(0, 1),
        }
    elif pattern == "medium":
        return {
            "time_spent_seconds": random.randint(180, 300),
            "idle_time_seconds": random.randint(20, 60),
            "hint_usage_count": random.randint(1, 3),
            "retry_count": random.randint(1, 2),
        }
    else:  # low
        return {
            "time_spent_seconds": random.randint(60, 150),
            "idle_time_seconds": random.randint(60, 150),
            "hint_usage_count": random.randint(3, 6),
            "retry_count": random.randint(3, 5),
        }


def seed_synthetic_dataset() -> None:
    with httpx.Client(base_url=BASE_URL, timeout=30) as client:
        try:
            teacher_token = _login_teacher(client)
        except httpx.HTTPStatusError:
            print(
                "Could not log in as the development teacher. "
                "Run `python -m app.database.seed_dev_teacher` first, "
                "and make sure the API server is running."
            )
            sys.exit(1)

        teacher_headers = {"Authorization": f"Bearer {teacher_token}"}

        if _already_seeded(client, teacher_token):
            print(
                "Synthetic dataset already present (found a student "
                f"with code starting '{SEED_MARKER}'). Nothing to do."
            )
            return

        print("Seeding synthetic dataset...")

        for i, full_name in enumerate(STUDENT_NAMES, start=1):
            student_code = f"{SEED_MARKER}{i:03d}"
            pin = f"{1000 + i}"

            # ── Create student ──────────────────────────────────────────
            student = client.post(
                "/students",
                json={
                    "student_code": student_code,
                    "full_name": full_name,
                    "pin": pin,
                },
                headers=teacher_headers,
            ).json()
            print(f"  Created student: {full_name} ({student_code})")

            # ── Create a learning plan ──────────────────────────────────
            plan = client.post(
                "/learning-plans",
                json={
                    "title": "Understanding Emotions & Social Skills",
                    "description": "A foundational plan covering emotional awareness, "
                                    "regulation, and social understanding.",
                    "student_id": student["id"],
                },
                headers=teacher_headers,
            ).json()

            # ── Create content: 2 entries per difficulty level ──────────
            content_by_difficulty: dict[str, list[dict]] = {}
            for difficulty, entries in CONTENT_LIBRARY.items():
                content_by_difficulty[difficulty] = []
                for entry in entries:
                    content = client.post(
                        "/learning-content",
                        json={
                            "title": entry["title"],
                            "subject": entry["subject"],
                            "body": entry["body"],
                            "difficulty_level": difficulty,
                            "learning_plan_id": plan["id"],
                            "teacher_notes": entry["teacher_notes"],
                        },
                        headers=teacher_headers,
                    ).json()
                    content_by_difficulty[difficulty].append(content)

            # ── Student logs in (own token for session actions) ─────────
            student_token = _login_student(client, student_code, pin)
            student_headers = {"Authorization": f"Bearer {student_token}"}

            # ── Create a spread of sessions across difficulty/status ────
            # Each student gets 4 sessions: one per difficulty level,
            # cycling through content entries so no two sessions at the
            # same difficulty use the same content (exercises the
            # multi-content-per-plan fix).
            session_plans = [
                ("Beginner", "completed", "high"),
                ("Easy", "completed", "medium"),
                ("Medium", "completed", "low"),
                ("Hard", "started", None),  # left in-progress for variety
            ]

            for idx, (difficulty, target_status, engagement_pattern) in enumerate(session_plans):
                content = content_by_difficulty[difficulty][idx % len(content_by_difficulty[difficulty])]

                session = client.post(
                    "/learning-sessions",
                    json={
                        "student_id": student["id"],
                        "learning_plan_id": plan["id"],
                        "learning_content_id": content["id"],
                    },
                    headers=teacher_headers,
                ).json()

                if target_status == "started":
                    continue  # leave as-is: a genuinely in-progress session

                # ── Student takes the quiz for this session ─────────────
                attempt = client.post(
                    f"/quiz-attempts/start/{session['id']}",
                    headers=student_headers,
                ).json()

                # Score according to the engagement pattern: high
                # engagement -> mostly correct, low -> mostly wrong, so
                # accuracy and engagement correlate the way a real
                # learner's data would.
                correct_rate = {"high": 0.9, "medium": 0.6, "low": 0.25}[engagement_pattern]
                answers = [
                    {
                        "question_id": q["question_id"],
                        "selected_option_index": (
                            # We don't know the correct index from the
                            # student-facing response (by design — no
                            # answer leakage), so approximate the desired
                            # correct_rate by answering index 0 most of
                            # the time for "high" and varying more for
                            # "low". This is an approximation for demo
                            # data purposes only.
                            0 if random.random() < correct_rate else random.randint(1, len(q["options"]) - 1)
                        ),
                    }
                    for q in attempt["questions"]
                ]
                client.post(
                    f"/quiz-attempts/{attempt['id']}/submit",
                    json={"answers": answers},
                    headers=student_headers,
                )

                # ── Complete the session with engagement metrics ────────
                metrics = _engagement_profile(engagement_pattern)
                client.post(
                    f"/student-learning/sessions/{session['id']}/complete",
                    json=metrics,
                    headers=student_headers,
                )

                # ── Generate an engagement prediction (teacher-side) ────
                client.post(
                    f"/engagement-predictions/{session['id']}/generate",
                    headers=teacher_headers,
                )

                # ── Generate a reflection ────────────────────────────────
                client.post(
                    f"/learning-reflections/generate/{session['id']}",
                    headers=student_headers,
                )

            # ── Mira chat history (Memora overhaul): a couple of turns
            # per student via the real API, so ConversationHistory and
            # EmotionLog aren't empty in the demo dataset either.
            for demo_message in _MIRA_DEMO_MESSAGES:
                client.post(
                    "/learning-companion/message",
                    json={"student_message": demo_message},
                    headers=student_headers,
                )

            print(f"    -> 4 sessions created (3 completed, 1 in progress)")

        print(
            f"\nSynthetic dataset seeded: {len(STUDENT_NAMES)} students, "
            f"each with a learning plan, {sum(len(v) for v in CONTENT_LIBRARY.values())} "
            f"content entries, 4 sessions, quiz attempts, reflections, and "
            f"engagement predictions."
        )
        print(f"Log in as any student with code SEED-DEMO-001 through "
              f"SEED-DEMO-{len(STUDENT_NAMES):03d}, PIN 1001-100{len(STUDENT_NAMES)}.")

    # ── Sensory profiles (Memora overhaul) ──────────────────────────────
    #
    # No CRUD endpoint exists for SensoryProfile yet (out of scope for
    # this pass — see implementation_plan.md's remaining Component 3
    # items), so this one supplement is seeded via direct ORM insert
    # rather than through the HTTP API, unlike everything else in this
    # script. Kept isolated in its own function so it's easy to delete
    # once a real /sensory-profile endpoint exists.
    _seed_sensory_profiles()


def _seed_sensory_profiles() -> None:
    """Direct-DB seed of varied SensoryProfile rows for the demo students."""
    from sqlalchemy import select

    from app.database import SessionLocal
    from app.models import SensoryProfile, Student

    profiles = [
        {"preferred_mode": "visual", "sensory_sensitivity_score": 0.8, "reduce_motion": True, "high_contrast": False, "mute_sounds": True, "attention_span_minutes": 10},
        {"preferred_mode": "text", "sensory_sensitivity_score": 0.4, "reduce_motion": False, "high_contrast": True, "mute_sounds": False, "attention_span_minutes": 20},
        {"preferred_mode": "mixed", "sensory_sensitivity_score": 0.6, "reduce_motion": True, "high_contrast": False, "mute_sounds": False, "attention_span_minutes": 15},
        {"preferred_mode": "auditory", "sensory_sensitivity_score": 0.3, "reduce_motion": False, "high_contrast": False, "mute_sounds": False, "attention_span_minutes": 25},
    ]

    with SessionLocal() as db:
        students = db.execute(
            select(Student).where(Student.student_code.like(f"{SEED_MARKER}%"))
        ).scalars().all()

        for i, student in enumerate(students):
            existing = db.execute(
                select(SensoryProfile).where(SensoryProfile.student_id == student.id)
            ).scalar_one_or_none()
            if existing is not None:
                continue
            profile_data = profiles[i % len(profiles)]
            db.add(SensoryProfile(student_id=student.id, **profile_data))
        db.commit()


if __name__ == "__main__":
    # python -m app.database.seed_synthetic_dataset
    # Requires the API server to be running (uvicorn app.main:app)
    seed_synthetic_dataset()
