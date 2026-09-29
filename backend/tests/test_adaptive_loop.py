"""
tests/test_adaptive_loop.py

Formalizes the manual end-to-end verification done in Phase 16 Ticket D:
learning session -> student sees it in Today's Learning -> the Phase 15
adaptive recommendation is correctly wired for the student.

This is a REGRESSION test for already-frozen Phase 15 modules, not new
coverage of new logic — it exists so this chain can be re-verified
automatically instead of via manual curl sessions.
"""

from __future__ import annotations

from tests.conftest import auth_header


def test_session_appears_in_students_today(client, student_token, seeded_session):
    response = client.get("/student-learning/today", headers=auth_header(student_token))
    assert response.status_code == 200
    session_ids = [s["id"] for s in response.json()]
    assert seeded_session["id"] in session_ids


def test_session_content_returns_the_exact_assigned_content(
    client, student_token, seeded_session
):
    """
    GET /sessions/{id}/content must return the specific content the
    session was created with (session["learning_content_id"]) — not
    whatever the recommendation engine currently considers the best
    match for the plan.
    """
    response = client.get(
        f"/student-learning/sessions/{seeded_session['id']}/content",
        headers=auth_header(student_token),
    )
    assert response.status_code == 200
    body = response.json()
    assert body["id"] == seeded_session["learning_content_id"]
    assert body["title"] == "Fixture Lesson"


def test_session_content_is_stable_across_multiple_plan_content_entries(
    client, student_token, teacher_token, seeded_student
):
    """
    Regression test for the exact bug reported: when a plan has more
    than one active piece of content at the same difficulty level, a
    session must always show the SPECIFIC content it was assigned —
    never silently substitute a different entry from the same plan
    (which is what calling the recommendation engine here used to do,
    since it always resolves ties to the lowest content id).
    """
    plan = client.post(
        "/learning-plans",
        json={"title": "Multi-Content Plan", "student_id": seeded_student.id},
        headers=auth_header(teacher_token),
    ).json()

    # Two pieces of content, same difficulty level — this is exactly the
    # scenario where the old recommendation-based lookup always
    # returned the first (lowest id) one regardless of which session
    # was actually being viewed.
    content_a = client.post(
        "/learning-content",
        json={
            "title": "Lesson A",
            "body": "Lesson A body text with enough words to qualify.",
            "difficulty_level": "Beginner",
            "learning_plan_id": plan["id"],
        },
        headers=auth_header(teacher_token),
    ).json()

    content_b = client.post(
        "/learning-content",
        json={
            "title": "Lesson B",
            "body": "Lesson B body text, completely different content.",
            "difficulty_level": "Beginner",
            "learning_plan_id": plan["id"],
        },
        headers=auth_header(teacher_token),
    ).json()

    # A session explicitly assigned to the SECOND content entry
    session_b = client.post(
        "/learning-sessions",
        json={
            "student_id": seeded_student.id,
            "learning_plan_id": plan["id"],
            "learning_content_id": content_b["id"],
        },
        headers=auth_header(teacher_token),
    ).json()

    response = client.get(
        f"/student-learning/sessions/{session_b['id']}/content",
        headers=auth_header(student_token),
    )
    assert response.status_code == 200
    body = response.json()
    # Must be Lesson B, not Lesson A — even though Lesson A has the
    # lower id and would be the recommendation engine's pick.
    assert body["id"] == content_b["id"]
    assert body["title"] == "Lesson B"
    assert body["id"] != content_a["id"]


def test_session_content_wrong_student_404(client, student_token):
    response = client.get(
        "/student-learning/sessions/999999/content",
        headers=auth_header(student_token),
    )
    assert response.status_code == 404


def test_recommended_content_matches_student_difficulty(client, student_token, seeded_session):
    """
    The seeded_session fixture creates content at 'Beginner' difficulty
    for a student whose current_difficulty_level is also 'Beginner'
    (conftest.seeded_student) — the recommendation engine should surface
    it as a match, with an explainable reason attached.
    """
    plan_id = seeded_session["learning_plan_id"]
    response = client.get(
        f"/student-learning/plans/{plan_id}/recommended-content",
        headers=auth_header(student_token),
    )
    assert response.status_code == 200
    body = response.json()
    assert body["content"] is not None
    assert body["content"]["difficulty_level"] == "Beginner"
    assert isinstance(body["reasoning"], str) and len(body["reasoning"]) > 0


def test_student_cannot_get_recommended_content_for_unowned_plan(
    client, student_token, teacher_token, seeded_student
):
    """A student must not be able to pull recommended content for a plan
    that isn't theirs, even if it exists and belongs to their own
    teacher (belongs to a different, unrelated student here)."""
    other_student_plan = client.post(
        "/students",
        json={"student_code": "OTHERKID", "full_name": "Other Kid", "pin": "4321"},
        headers=auth_header(teacher_token),
    ).json()
    plan = client.post(
        "/learning-plans",
        json={"title": "Not Yours", "student_id": other_student_plan["id"]},
        headers=auth_header(teacher_token),
    ).json()

    response = client.get(
        f"/student-learning/plans/{plan['id']}/recommended-content",
        headers=auth_header(student_token),
    )
    assert response.status_code == 404


def test_student_complete_session_updates_status(client, student_token, seeded_session):
    response = client.post(
        f"/student-learning/sessions/{seeded_session['id']}/complete",
        json={},
        headers=auth_header(student_token),
    )
    assert response.status_code == 200
    assert response.json()["status"] == "completed"

    all_sessions = client.get(
        "/student-learning/sessions", headers=auth_header(student_token)
    ).json()
    completed = next(s for s in all_sessions if s["id"] == seeded_session["id"])
    assert completed["status"] == "completed"
