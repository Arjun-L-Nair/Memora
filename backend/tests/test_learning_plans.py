"""tests/test_learning_plans.py — /learning-plans regression + ownership."""

from __future__ import annotations

from tests.conftest import auth_header


def test_create_learning_plan(client, teacher_token, seeded_student):
    response = client.post(
        "/learning-plans",
        json={"title": "Reading Basics", "student_id": seeded_student.id},
        headers=auth_header(teacher_token),
    )
    assert response.status_code == 201
    body = response.json()
    assert body["title"] == "Reading Basics"
    assert body["student_id"] == seeded_student.id
    assert body["is_active"] is True


def test_create_learning_plan_for_unowned_student_404(client, teacher_token, seeded_student, second_teacher_token):
    """seeded_student belongs to seeded_teacher; teacher2 must not be able
    to create a plan against them (would let a teacher enumerate/target
    another teacher's students)."""
    response = client.post(
        "/learning-plans",
        json={"title": "Sneaky Plan", "student_id": seeded_student.id},
        headers=auth_header(second_teacher_token),
    )
    assert response.status_code == 404


def test_list_learning_plans_scoped_to_owner(client, teacher_token, second_teacher_token, seeded_student):
    client.post(
        "/learning-plans",
        json={"title": "Owner's Plan", "student_id": seeded_student.id},
        headers=auth_header(teacher_token),
    )
    other_list = client.get("/learning-plans", headers=auth_header(second_teacher_token))
    assert other_list.status_code == 200
    assert other_list.json() == []

    own_list = client.get("/learning-plans", headers=auth_header(teacher_token))
    assert any(p["title"] == "Owner's Plan" for p in own_list.json())


def test_update_learning_plan(client, teacher_token, seeded_student):
    created = client.post(
        "/learning-plans",
        json={"title": "Original Title", "student_id": seeded_student.id},
        headers=auth_header(teacher_token),
    ).json()

    response = client.patch(
        f"/learning-plans/{created['id']}",
        json={"title": "Renamed Title"},
        headers=auth_header(teacher_token),
    )
    assert response.status_code == 200
    assert response.json()["title"] == "Renamed Title"


def test_deactivate_learning_plan(client, teacher_token, seeded_student):
    created = client.post(
        "/learning-plans",
        json={"title": "To Deactivate", "student_id": seeded_student.id},
        headers=auth_header(teacher_token),
    ).json()

    response = client.post(
        f"/learning-plans/{created['id']}/deactivate", headers=auth_header(teacher_token)
    )
    assert response.status_code == 200
    assert response.json()["is_active"] is False


def test_get_nonexistent_learning_plan_404(client, teacher_token):
    response = client.get("/learning-plans/999999", headers=auth_header(teacher_token))
    assert response.status_code == 404
