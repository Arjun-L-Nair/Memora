"""tests/test_learning_content.py — /learning-content regression + ownership."""

from __future__ import annotations

import pytest

from tests.conftest import auth_header


@pytest.fixture
def seeded_plan(client, teacher_token, seeded_student):
    response = client.post(
        "/learning-plans",
        json={"title": "Content Test Plan", "student_id": seeded_student.id},
        headers=auth_header(teacher_token),
    )
    return response.json()


def test_create_learning_content(client, teacher_token, seeded_plan):
    response = client.post(
        "/learning-content",
        json={
            "title": "Intro Lesson",
            "body": "Lesson body text.",
            "difficulty_level": "Beginner",
            "learning_plan_id": seeded_plan["id"],
        },
        headers=auth_header(teacher_token),
    )
    assert response.status_code == 201
    assert response.json()["difficulty_level"] == "Beginner"


def test_create_content_rejects_invalid_difficulty(client, teacher_token, seeded_plan):
    """difficulty_level is a constrained Literal — an out-of-range value
    must be a 422 validation error, not silently accepted."""
    response = client.post(
        "/learning-content",
        json={
            "title": "Bad Difficulty",
            "body": "Text.",
            "difficulty_level": "Impossible",
            "learning_plan_id": seeded_plan["id"],
        },
        headers=auth_header(teacher_token),
    )
    assert response.status_code == 422


def test_create_content_for_unowned_plan_404(client, second_teacher_token, seeded_plan):
    response = client.post(
        "/learning-content",
        json={
            "title": "Sneaky Content",
            "body": "Text.",
            "difficulty_level": "Beginner",
            "learning_plan_id": seeded_plan["id"],
        },
        headers=auth_header(second_teacher_token),
    )
    assert response.status_code == 404


def test_update_learning_content(client, teacher_token, seeded_plan):
    created = client.post(
        "/learning-content",
        json={
            "title": "Original",
            "body": "Text.",
            "difficulty_level": "Beginner",
            "learning_plan_id": seeded_plan["id"],
        },
        headers=auth_header(teacher_token),
    ).json()

    response = client.patch(
        f"/learning-content/{created['id']}",
        json={"difficulty_level": "Medium"},
        headers=auth_header(teacher_token),
    )
    assert response.status_code == 200
    assert response.json()["difficulty_level"] == "Medium"


def test_deactivate_learning_content(client, teacher_token, seeded_plan):
    created = client.post(
        "/learning-content",
        json={
            "title": "To Deactivate",
            "body": "Text.",
            "difficulty_level": "Beginner",
            "learning_plan_id": seeded_plan["id"],
        },
        headers=auth_header(teacher_token),
    ).json()

    response = client.post(
        f"/learning-content/{created['id']}/deactivate", headers=auth_header(teacher_token)
    )
    assert response.status_code == 200
    assert response.json()["is_active"] is False


def test_list_content_filtered_by_plan(client, teacher_token, seeded_plan):
    client.post(
        "/learning-content",
        json={
            "title": "Filtered Lesson",
            "body": "Text.",
            "difficulty_level": "Beginner",
            "learning_plan_id": seeded_plan["id"],
        },
        headers=auth_header(teacher_token),
    )
    response = client.get(
        f"/learning-content?learning_plan_id={seeded_plan['id']}",
        headers=auth_header(teacher_token),
    )
    assert response.status_code == 200
    assert all(c["learning_plan_id"] == seeded_plan["id"] for c in response.json())
