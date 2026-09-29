"""
tests/test_reflection.py

Covers Phase 16 Section 10 (Learning Reflection) and part of Section 9
(Ollama reliability — fallback path, naturally exercised since no
Ollama server runs in the test environment).
"""

from __future__ import annotations

from tests.conftest import auth_header


def test_generate_reflection_uses_fallback(client, student_token, seeded_session):
    response = client.post(
        f"/learning-reflections/generate/{seeded_session['id']}",
        headers=auth_header(student_token),
    )
    assert response.status_code == 201
    body = response.json()
    assert body["learning_session_id"] == seeded_session["id"]
    assert body["generated_by"] == "template"
    assert len(body["content"]) > 0


def test_generate_reflection_twice_conflicts(client, student_token, seeded_session):
    first = client.post(
        f"/learning-reflections/generate/{seeded_session['id']}",
        headers=auth_header(student_token),
    )
    assert first.status_code == 201

    second = client.post(
        f"/learning-reflections/generate/{seeded_session['id']}",
        headers=auth_header(student_token),
    )
    assert second.status_code == 409


def test_get_reflection_by_id(client, student_token, seeded_session):
    created = client.post(
        f"/learning-reflections/generate/{seeded_session['id']}",
        headers=auth_header(student_token),
    ).json()

    response = client.get(
        f"/learning-reflections/{created['id']}", headers=auth_header(student_token)
    )
    assert response.status_code == 200
    assert response.json()["id"] == created["id"]


def test_generate_reflection_nonexistent_session_404(client, student_token):
    response = client.post(
        "/learning-reflections/generate/999999", headers=auth_header(student_token)
    )
    assert response.status_code == 404


def test_get_reflection_by_session_null_before_generate(client, student_token, seeded_session):
    """No reflection yet -> the by-session lookup returns null, not a 404 or error."""
    response = client.get(
        f"/learning-reflections/by-session/{seeded_session['id']}",
        headers=auth_header(student_token),
    )
    assert response.status_code == 200
    assert response.json() is None


def test_get_reflection_by_session_resumes_existing(client, student_token, seeded_session):
    """Once generated, the by-session lookup returns the existing reflection."""
    created = client.post(
        f"/learning-reflections/generate/{seeded_session['id']}",
        headers=auth_header(student_token),
    ).json()

    resumed = client.get(
        f"/learning-reflections/by-session/{seeded_session['id']}",
        headers=auth_header(student_token),
    )
    assert resumed.status_code == 200
    assert resumed.json()["id"] == created["id"]


def test_get_reflection_by_session_wrong_student_404(client, student_token):
    response = client.get(
        "/learning-reflections/by-session/999999", headers=auth_header(student_token)
    )
    assert response.status_code == 404
