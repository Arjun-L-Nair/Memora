"""
tests/test_quiz.py

Covers Phase 16 Section 11 (Quiz Workflow) and part of Section 9
(Ollama reliability — the fallback path, which is this environment's
natural state since no Ollama server is running during tests).
"""

from __future__ import annotations

from tests.conftest import auth_header


def test_start_quiz_attempt_uses_template_fallback(client, student_token, seeded_session):
    """
    No Ollama server is reachable in the test environment, so this
    exercises the real fallback path (not a mock) — the same behavior
    Phase 16 Section 9 requires when Ollama is unavailable.
    """
    response = client.post(
        f"/quiz-attempts/start/{seeded_session['id']}", headers=auth_header(student_token)
    )
    assert response.status_code == 201
    body = response.json()
    assert body["quiz_source"] == "template_fallback"
    assert body["total_questions"] == len(body["questions"]) > 0
    assert body["submitted_at"] is None
    # The answer key must never be sent to the client.
    for question in body["questions"]:
        assert "correct_option_index" not in question
        assert "answer" not in question


def test_start_quiz_attempt_twice_conflicts(client, student_token, seeded_session):
    first = client.post(
        f"/quiz-attempts/start/{seeded_session['id']}", headers=auth_header(student_token)
    )
    assert first.status_code == 201

    second = client.post(
        f"/quiz-attempts/start/{seeded_session['id']}", headers=auth_header(student_token)
    )
    assert second.status_code == 409


def test_submit_quiz_attempt_scores_and_locks(client, student_token, seeded_session):
    started = client.post(
        f"/quiz-attempts/start/{seeded_session['id']}", headers=auth_header(student_token)
    ).json()

    answers = [
        {"question_id": q["question_id"], "selected_option_index": 0}
        for q in started["questions"]
    ]
    submitted = client.post(
        f"/quiz-attempts/{started['id']}/submit",
        json={"answers": answers},
        headers=auth_header(student_token),
    )
    assert submitted.status_code == 200
    body = submitted.json()
    assert body["submitted_at"] is not None
    assert body["score"] is not None
    assert body["accuracy"] is not None


def test_submit_quiz_attempt_records_hint_usage_on_session(
    client, student_token, teacher_token, seeded_session
):
    """
    Regression test for a real, previously-unmeasured engagement
    signal: using a hint on a question must increment the linked
    session's hint_usage_count by the number of hinted questions in
    this submission — this is what makes hint-seeking behaviour real,
    measured data feeding the engagement-prediction model, rather than
    a database column that only ever received synthetic/seeded values.
    """
    started = client.post(
        f"/quiz-attempts/start/{seeded_session['id']}", headers=auth_header(student_token)
    ).json()

    questions = started["questions"]
    answers = [
        {
            "question_id": q["question_id"],
            "selected_option_index": 0,
            "hint_used": i < 2,  # hint used on the first 2 questions only
        }
        for i, q in enumerate(questions)
    ]

    client.post(
        f"/quiz-attempts/{started['id']}/submit",
        json={"answers": answers},
        headers=auth_header(student_token),
    )

    session = client.get(
        f"/learning-sessions/{seeded_session['id']}", headers=auth_header(teacher_token)
    ).json()
    assert session["hint_usage_count"] == 2


def test_submit_quiz_attempt_without_hints_leaves_count_at_zero(
    client, student_token, teacher_token, seeded_session
):
    """hint_used defaults to False — a submission with no hints used at
    all must not spuriously increment hint_usage_count."""
    started = client.post(
        f"/quiz-attempts/start/{seeded_session['id']}", headers=auth_header(student_token)
    ).json()

    answers = [
        {"question_id": q["question_id"], "selected_option_index": 0}
        for q in started["questions"]
    ]
    client.post(
        f"/quiz-attempts/{started['id']}/submit",
        json={"answers": answers},
        headers=auth_header(student_token),
    )

    session = client.get(
        f"/learning-sessions/{seeded_session['id']}", headers=auth_header(teacher_token)
    ).json()
    assert session["hint_usage_count"] == 0


def test_get_hint_returns_a_wrong_option_index(client, student_token, seeded_session):
    """
    The hint endpoint must return a valid, in-range option index that
    is NOT the correct answer — but since QuizQuestionOut never exposes
    the correct index to the test's own client either, this test
    verifies the returned index is structurally valid and that the
    same question consistently returns the same eliminated index
    (deterministic, not random).
    """
    started = client.post(
        f"/quiz-attempts/start/{seeded_session['id']}", headers=auth_header(student_token)
    ).json()
    question = started["questions"][0]

    first = client.get(
        f"/quiz-attempts/{started['id']}/hint/{question['question_id']}",
        headers=auth_header(student_token),
    )
    assert first.status_code == 200
    body = first.json()
    assert body["question_id"] == question["question_id"]
    assert 0 <= body["eliminated_option_index"] < len(question["options"])

    # Deterministic: requesting again for the same question returns the
    # same eliminated index every time.
    second = client.get(
        f"/quiz-attempts/{started['id']}/hint/{question['question_id']}",
        headers=auth_header(student_token),
    )
    assert second.json()["eliminated_option_index"] == body["eliminated_option_index"]


def test_get_hint_for_unknown_question_404s(client, student_token, seeded_session):
    started = client.post(
        f"/quiz-attempts/start/{seeded_session['id']}", headers=auth_header(student_token)
    ).json()

    response = client.get(
        f"/quiz-attempts/{started['id']}/hint/not-a-real-question-id",
        headers=auth_header(student_token),
    )
    assert response.status_code == 404


def test_get_hint_after_submission_conflicts(client, student_token, seeded_session):
    started = client.post(
        f"/quiz-attempts/start/{seeded_session['id']}", headers=auth_header(student_token)
    ).json()
    question = started["questions"][0]

    answers = [
        {"question_id": q["question_id"], "selected_option_index": 0}
        for q in started["questions"]
    ]
    client.post(
        f"/quiz-attempts/{started['id']}/submit",
        json={"answers": answers},
        headers=auth_header(student_token),
    )

    response = client.get(
        f"/quiz-attempts/{started['id']}/hint/{question['question_id']}",
        headers=auth_header(student_token),
    )
    assert response.status_code == 409


def test_get_hint_nonexistent_attempt_404s(client, student_token):
    response = client.get(
        "/quiz-attempts/999999/hint/some-question-id",
        headers=auth_header(student_token),
    )
    assert response.status_code == 404


def test_submit_quiz_attempt_twice_conflicts(client, student_token, seeded_session):
    started = client.post(
        f"/quiz-attempts/start/{seeded_session['id']}", headers=auth_header(student_token)
    ).json()
    answers = [
        {"question_id": q["question_id"], "selected_option_index": 0}
        for q in started["questions"]
    ]
    client.post(
        f"/quiz-attempts/{started['id']}/submit",
        json={"answers": answers},
        headers=auth_header(student_token),
    )

    second_submit = client.post(
        f"/quiz-attempts/{started['id']}/submit",
        json={"answers": answers},
        headers=auth_header(student_token),
    )
    assert second_submit.status_code == 409


def test_teacher_can_read_but_not_start_quiz(client, teacher_token, student_token, seeded_session):
    started = client.post(
        f"/quiz-attempts/start/{seeded_session['id']}", headers=auth_header(student_token)
    ).json()

    teacher_read = client.get(
        f"/quiz-attempts/teacher/{started['id']}", headers=auth_header(teacher_token)
    )
    assert teacher_read.status_code == 200

    # Teachers have no start endpoint at all — get_current_student
    # dependency rejects a teacher token outright.
    teacher_start_attempt = client.post(
        f"/quiz-attempts/start/{seeded_session['id']}", headers=auth_header(teacher_token)
    )
    assert teacher_start_attempt.status_code in (401, 403)


def test_get_quiz_attempt_by_session_null_before_start(client, student_token, seeded_session):
    """No attempt yet -> the by-session lookup returns null, not a 404 or error."""
    response = client.get(
        f"/quiz-attempts/by-session/{seeded_session['id']}", headers=auth_header(student_token)
    )
    assert response.status_code == 200
    assert response.json() is None


def test_get_quiz_attempt_by_session_resumes_existing(client, student_token, seeded_session):
    """
    Once an attempt exists (started, or started-then-submitted), the
    by-session lookup returns it instead of forcing the caller through
    a failing POST /start call to discover it exists.
    """
    started = client.post(
        f"/quiz-attempts/start/{seeded_session['id']}", headers=auth_header(student_token)
    ).json()

    resumed = client.get(
        f"/quiz-attempts/by-session/{seeded_session['id']}", headers=auth_header(student_token)
    )
    assert resumed.status_code == 200
    assert resumed.json()["id"] == started["id"]
    assert resumed.json()["submitted_at"] is None


def test_get_quiz_attempt_by_session_wrong_student_404(client, student_token):
    """A session that isn't this student's own raises 404, not a leak."""
    response = client.get(
        "/quiz-attempts/by-session/999999", headers=auth_header(student_token)
    )
    assert response.status_code == 404


def test_start_quiz_nonexistent_session_404(client, student_token):
    response = client.post("/quiz-attempts/start/999999", headers=auth_header(student_token))
    assert response.status_code == 404
