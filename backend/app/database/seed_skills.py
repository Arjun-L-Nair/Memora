"""
database/seed_skills.py

Seeds the predefined skills library: 3 Easy, 5 Medium, 7 Hard skills,
each with 3 hand-written multiple-choice exercises (45 total).

Deliberately NOT AI-generated (see models/skill_exercise.py's
docstring) — a small, fixed, hand-curated practice set, consistent
with this project's "predictability over novelty" design philosophy
for autistic learners.

Idempotent: safe to run multiple times. If any skills already exist,
this exits without making changes rather than creating duplicates —
run it once per fresh database (it's called automatically from
app/database/init_db.py's startup sequence, mirroring the dev-admin
bootstrap pattern already used there).
"""

from __future__ import annotations

import json
import logging

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Skill, SkillExercise

logger = logging.getLogger("memora.seed_skills")


def _exercise(prompt: str, options: list[str], correct_index: int, order: int) -> dict:
    return {
        "prompt": prompt,
        "options_json": json.dumps(options),
        "correct_option_index": correct_index,
        "order_index": order,
    }


# ─── EASY (3 skills) ────────────────────────────────────────────────────────
_EASY_SKILLS = [
    {
        "name": "Pattern Recognition",
        "description": "Spot what comes next in a simple repeating pattern.",
        "category": "pattern",
        "exercises": [
            _exercise("What comes next? 🔵 🔴 🔵 🔴 🔵 ___", ["🔵", "🔴", "🟢", "🟡"], 1, 0),
            _exercise("What comes next? ⭐ ⭐ 🌙 ⭐ ⭐ 🌙 ⭐ ⭐ ___", ["⭐", "🌙", "☀️", "⛅"], 1, 1),
            _exercise("What comes next? 1, 2, 1, 2, 1, ___", ["1", "2", "3", "0"], 1, 2),
        ],
    },
    {
        "name": "Number Sequences",
        "description": "Practice counting forward and skip-counting.",
        "category": "math",
        "exercises": [
            _exercise("What comes next? 2, 4, 6, 8, ___", ["9", "10", "12", "11"], 1, 0),
            _exercise("What comes next? 5, 10, 15, ___", ["18", "20", "25", "16"], 1, 1),
            _exercise("What comes next? 10, 9, 8, 7, ___", ["5", "6", "8", "9"], 1, 2),
        ],
    },
    {
        "name": "Shape Matching",
        "description": "Identify shapes that match by type or color.",
        "category": "shapes",
        "exercises": [
            _exercise("Which shape has 3 sides?", ["Square", "Triangle", "Circle", "Pentagon"], 1, 0),
            _exercise("Which shape has NO corners?", ["Circle", "Square", "Triangle", "Rectangle"], 0, 1),
            _exercise("Which shape has 4 equal sides?", ["Triangle", "Circle", "Square", "Oval"], 2, 2),
        ],
    },
]

# ─── MEDIUM (5 skills) ──────────────────────────────────────────────────────
_MEDIUM_SKILLS = [
    {
        "name": "Basic Addition & Subtraction",
        "description": "Solve simple one and two-digit addition and subtraction problems.",
        "category": "math",
        "exercises": [
            _exercise("What is 7 + 5?", ["11", "12", "13", "10"], 1, 0),
            _exercise("What is 15 - 6?", ["8", "9", "10", "7"], 1, 1),
            _exercise("What is 9 + 8?", ["16", "17", "18", "15"], 1, 2),
        ],
    },
    {
        "name": "Word Categorization",
        "description": "Sort words into the category they belong to.",
        "category": "logic",
        "exercises": [
            _exercise("Which word is a fruit?", ["Carrot", "Apple", "Potato", "Broccoli"], 1, 0),
            _exercise("Which word is an animal?", ["Table", "Dog", "Chair", "Lamp"], 1, 1),
            _exercise("Which word is a color?", ["Blue", "Happy", "Run", "Book"], 0, 2),
        ],
    },
    {
        "name": "Simple Logic",
        "description": "Practice basic if-then reasoning.",
        "category": "logic",
        "exercises": [
            _exercise("If it is raining, you should bring a(n) ___.", ["Umbrella", "Sunglasses", "Fan", "Kite"], 0, 0),
            _exercise("If you are tired, you should ___.", ["Run fast", "Rest", "Shout", "Jump"], 1, 1),
            _exercise("If the light is red, you should ___.", ["Go", "Stop", "Jump", "Sing"], 1, 2),
        ],
    },
    {
        "name": "Time Telling",
        "description": "Read and understand clock times.",
        "category": "time",
        "exercises": [
            _exercise("How many minutes are in one hour?", ["30", "45", "60", "90"], 2, 0),
            _exercise("If it is 3:00, what time is it in 1 hour?", ["3:30", "4:00", "2:00", "5:00"], 1, 1),
            _exercise("How many hours are in one day?", ["12", "20", "24", "48"], 2, 2),
        ],
    },
    {
        "name": "Money Counting",
        "description": "Practice counting coins and simple bill values.",
        "category": "math",
        "exercises": [
            _exercise("How many cents are in one dollar?", ["10", "50", "100", "1000"], 2, 0),
            _exercise("If you have 2 quarters, how many cents do you have?", ["25", "50", "75", "100"], 1, 1),
            _exercise("Which is worth more?", ["1 dime", "1 nickel", "1 quarter", "1 penny"], 2, 2),
        ],
    },
]

# ─── HARD (7 skills) ────────────────────────────────────────────────────────
_HARD_SKILLS = [
    {
        "name": "Multiplication & Division",
        "description": "Solve basic multiplication and division problems.",
        "category": "math",
        "exercises": [
            _exercise("What is 6 x 7?", ["36", "42", "48", "40"], 1, 0),
            _exercise("What is 45 / 9?", ["4", "5", "6", "9"], 1, 1),
            _exercise("What is 8 x 8?", ["56", "60", "64", "72"], 2, 2),
        ],
    },
    {
        "name": "Multi-Step Word Problems",
        "description": "Solve word problems that need more than one step.",
        "category": "math",
        "exercises": [
            _exercise(
                "Sam has 3 boxes with 4 apples each. He eats 2 apples. How many apples are left?",
                ["9", "10", "12", "14"],
                1,
                0,
            ),
            _exercise(
                "A shelf holds 5 books. There are 4 shelves, but 1 shelf is empty. How many books total?",
                ["15", "20", "16", "25"],
                0,
                1,
            ),
            _exercise(
                "Maya had $20. She spent $8 on lunch and $5 on a book. How much money is left?",
                ["$5", "$7", "$8", "$12"],
                1,
                2,
            ),
        ],
    },
    {
        "name": "Fractions",
        "description": "Understand and compare simple fractions.",
        "category": "math",
        "exercises": [
            _exercise("Which fraction is the largest?", ["1/4", "1/2", "1/8", "1/3"], 1, 0),
            _exercise("What is 1/2 + 1/4?", ["1/6", "2/6", "3/4", "1/4"], 2, 1),
            _exercise("If a pizza has 8 slices and you eat 4, what fraction did you eat?", ["1/8", "1/4", "1/2", "3/4"], 2, 2),
        ],
    },
    {
        "name": "Data Reading",
        "description": "Read information from simple charts and tables.",
        "category": "logic",
        "exercises": [
            _exercise(
                "A chart shows: Monday=3 books, Tuesday=5 books, Wednesday=2 books. Which day had the most?",
                ["Monday", "Tuesday", "Wednesday", "They're equal"],
                1,
                0,
            ),
            _exercise(
                "A chart shows: Red=4 votes, Blue=7 votes, Green=2 votes. What is the total number of votes?",
                ["11", "13", "9", "15"],
                1,
                1,
            ),
            _exercise(
                "A chart shows temperatures rising each day: 60, 65, 70, 75. What is the pattern?",
                ["Decreasing by 5", "Increasing by 5", "Staying the same", "Random"],
                1,
                2,
            ),
        ],
    },
    {
        "name": "Advanced Pattern Recognition",
        "description": "Solve more complex number and symbol patterns.",
        "category": "pattern",
        "exercises": [
            _exercise("What comes next? 1, 4, 9, 16, ___", ["20", "24", "25", "36"], 2, 0),
            _exercise("What comes next? 2, 6, 18, 54, ___", ["108", "162", "150", "60"], 1, 1),
            _exercise("What comes next? A, C, E, G, ___", ["H", "I", "F", "J"], 1, 2),
        ],
    },
    {
        "name": "Basic Geometry",
        "description": "Calculate the perimeter and area of simple shapes.",
        "category": "shapes",
        "exercises": [
            _exercise("A square has sides of 4 cm. What is its perimeter?", ["8 cm", "12 cm", "16 cm", "20 cm"], 2, 0),
            _exercise("A rectangle is 5 cm by 3 cm. What is its area?", ["8 cm²", "15 cm²", "16 cm²", "10 cm²"], 1, 1),
            _exercise("How many sides does a hexagon have?", ["5", "6", "7", "8"], 1, 2),
        ],
    },
    {
        "name": "Logical Deduction",
        "description": "Use multiple clues together to find the answer.",
        "category": "logic",
        "exercises": [
            _exercise(
                "All cats are animals. Whiskers is a cat. What do we know about Whiskers?",
                ["Whiskers is a dog", "Whiskers is an animal", "Whiskers is a plant", "Nothing"],
                1,
                0,
            ),
            _exercise(
                "Tom is taller than Sam. Sam is taller than Ali. Who is the shortest?",
                ["Tom", "Sam", "Ali", "Can't tell"],
                2,
                1,
            ),
            _exercise(
                "If today is Wednesday, what day was it 2 days ago?",
                ["Monday", "Tuesday", "Thursday", "Friday"],
                1,
                2,
            ),
        ],
    },
]

_TIERS: list[tuple[str, list[dict]]] = [
    ("Easy", _EASY_SKILLS),
    ("Medium", _MEDIUM_SKILLS),
    ("Hard", _HARD_SKILLS),
]


def seed_skills(db: Session) -> None:
    """Seed the skills library if it's currently empty. Idempotent — a no-op if any skill already exists."""
    existing = db.execute(select(Skill.id).limit(1)).scalar_one_or_none()
    if existing is not None:
        logger.info("Skills library already seeded; skipping.")
        return

    for tier, skills in _TIERS:
        for order_index, skill_data in enumerate(skills):
            skill = Skill(
                name=skill_data["name"],
                description=skill_data["description"],
                tier=tier,
                category=skill_data["category"],
                order_index=order_index,
            )
            db.add(skill)
            db.flush()  # assign skill.id for the exercises below

            for exercise_data in skill_data["exercises"]:
                db.add(SkillExercise(skill_id=skill.id, **exercise_data))

    db.commit()
    total_skills = sum(len(skills) for _, skills in _TIERS)
    total_exercises = sum(len(s["exercises"]) for _, skills in _TIERS for s in skills)
    logger.info("Seeded skills library: %d skills, %d exercises.", total_skills, total_exercises)


def seed_skills_on_startup() -> None:
    """
    No-argument wrapper for use in app startup (main.py's lifespan) —
    opens and closes its own session, mirroring
    seed_dev_admin.seed_dev_admin()'s pattern. Unlike the dev-admin
    seed, this runs in EVERY environment including production: the
    skill library is real application content every deployment needs
    populated to function, not development-only convenience data.
    """
    from app.database.session import SessionLocal

    db = SessionLocal()
    try:
        seed_skills(db)
    finally:
        db.close()
