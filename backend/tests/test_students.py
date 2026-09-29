"""
tests/test_students.py

Covers Phase 16 Section 6 (API Contract) and Section 5 (ownership
isolation) for the /students router.
"""

from __future__ import annotations

from tests.conftest import auth_header


def test_create_and_list_student(client, teacher_token):
    create = client.post(
        "/students",
        json={"student_code": "S100", "full_name": "Alex Doe", "pin": "1111"},
        headers=auth_header(teacher_token),
    )
    assert create.status_code == 201
    body = create.json()
    assert body["student_code"] == "S100"
    assert body["is_active"] is True
    assert "pin" not in body and "pin_hash" not in body  # never leak the PIN

    listed = client.get("/students", headers=auth_header(teacher_token))
    assert listed.status_code == 200
    assert any(s["student_code"] == "S100" for s in listed.json())


def test_create_student_duplicate_code_conflicts(client, teacher_token, seeded_student):
    response = client.post(
        "/students",
        json={
            "student_code": seeded_student.student_code,
            "full_name": "Someone Else",
            "pin": "2222",
        },
        headers=auth_header(teacher_token),
    )
    assert response.status_code == 409


def test_get_single_student(client, teacher_token, seeded_student):
    response = client.get(f"/students/{seeded_student.id}", headers=auth_header(teacher_token))
    assert response.status_code == 200
    assert response.json()["id"] == seeded_student.id


def test_get_nonexistent_student_404(client, teacher_token):
    response = client.get("/students/999999", headers=auth_header(teacher_token))
    assert response.status_code == 404


def test_update_student(client, teacher_token, seeded_student):
    response = client.patch(
        f"/students/{seeded_student.id}",
        json={"full_name": "Updated Name"},
        headers=auth_header(teacher_token),
    )
    assert response.status_code == 200
    assert response.json()["full_name"] == "Updated Name"


def test_deactivate_student(client, teacher_token, seeded_student):
    response = client.post(
        f"/students/{seeded_student.id}/deactivate", headers=auth_header(teacher_token)
    )
    assert response.status_code == 200
    assert response.json()["is_active"] is False


def test_reset_student_pin(client, teacher_token, seeded_student):
    response = client.post(
        f"/students/{seeded_student.id}/reset-pin",
        json={"pin": "5678"},
        headers=auth_header(teacher_token),
    )
    assert response.status_code == 200

    # New PIN must now work for login; old one must not.
    old_login = client.post(
        "/auth/student/login",
        json={"student_code": seeded_student.student_code, "pin": "1234"},
    )
    assert old_login.status_code == 401

    new_login = client.post(
        "/auth/student/login",
        json={"student_code": seeded_student.student_code, "pin": "5678"},
    )
    assert new_login.status_code == 200


def test_teacher_cannot_see_another_teachers_student(
    client, second_teacher_token, seeded_student
):
    """Ownership isolation: seeded_student belongs to seeded_teacher, not
    seeded_second_teacher. A cross-owner GET must 404, not leak data."""
    response = client.get(
        f"/students/{seeded_student.id}", headers=auth_header(second_teacher_token)
    )
    assert response.status_code == 404


def test_teacher_cannot_deactivate_another_teachers_student(
    client, second_teacher_token, seeded_student
):
    response = client.post(
        f"/students/{seeded_student.id}/deactivate",
        headers=auth_header(second_teacher_token),
    )
    assert response.status_code == 404


def test_second_teacher_student_list_excludes_first_teachers_students(
    client, second_teacher_token, seeded_student
):
    response = client.get("/students", headers=auth_header(second_teacher_token))
    assert response.status_code == 200
    assert all(s["id"] != seeded_student.id for s in response.json())
