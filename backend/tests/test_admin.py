"""tests/test_admin.py — /admin router regression (teachers, students, stats)."""

from __future__ import annotations

from tests.conftest import auth_header


def test_admin_create_and_list_teacher(client, admin_token):
    created = client.post(
        "/admin/teachers",
        json={
            "full_name": "New Teacher",
            "email": "new.teacher@test.com",
            "password": "password123",
        },
        headers=auth_header(admin_token),
    )
    assert created.status_code == 201
    body = created.json()
    assert body["email"] == "new.teacher@test.com"
    assert body["is_active"] is True
    assert "password" not in body and "password_hash" not in body

    listed = client.get("/admin/teachers", headers=auth_header(admin_token))
    assert listed.status_code == 200
    assert any(t["email"] == "new.teacher@test.com" for t in listed.json())


def test_admin_create_teacher_duplicate_email_conflicts(client, admin_token, seeded_teacher):
    response = client.post(
        "/admin/teachers",
        json={
            "full_name": "Duplicate",
            "email": seeded_teacher.email,
            "password": "password123",
        },
        headers=auth_header(admin_token),
    )
    assert response.status_code == 409


def test_admin_deactivate_and_activate_teacher(client, admin_token, seeded_teacher):
    deactivated = client.post(
        f"/admin/teachers/{seeded_teacher.id}/deactivate", headers=auth_header(admin_token)
    )
    assert deactivated.status_code == 200
    assert deactivated.json()["is_active"] is False

    # A deactivated teacher must not be able to log in.
    login_attempt = client.post(
        "/auth/teacher/login",
        json={"email": seeded_teacher.email, "password": "password123"},
    )
    assert login_attempt.status_code == 401

    activated = client.post(
        f"/admin/teachers/{seeded_teacher.id}/activate", headers=auth_header(admin_token)
    )
    assert activated.status_code == 200
    assert activated.json()["is_active"] is True

    login_again = client.post(
        "/auth/teacher/login",
        json={"email": seeded_teacher.email, "password": "password123"},
    )
    assert login_again.status_code == 200


def test_admin_can_see_students_across_teachers(
    client, admin_token, teacher_token, second_teacher_token
):
    client.post(
        "/students",
        json={"student_code": "ADMSEE1", "full_name": "Teacher1 Student", "pin": "1111"},
        headers=auth_header(teacher_token),
    )
    client.post(
        "/students",
        json={"student_code": "ADMSEE2", "full_name": "Teacher2 Student", "pin": "2222"},
        headers=auth_header(second_teacher_token),
    )

    response = client.get("/admin/students", headers=auth_header(admin_token))
    assert response.status_code == 200
    codes = {s["student_code"] for s in response.json()}
    assert {"ADMSEE1", "ADMSEE2"}.issubset(codes)


def test_admin_stats_reflect_created_data(client, admin_token, teacher_token):
    before = client.get("/admin/stats", headers=auth_header(admin_token)).json()

    client.post(
        "/students",
        json={"student_code": "STATCHK", "full_name": "Stat Check", "pin": "3333"},
        headers=auth_header(teacher_token),
    )

    after = client.get("/admin/stats", headers=auth_header(admin_token)).json()
    assert after["total_students"] == before["total_students"] + 1
    assert after["active_students"] == before["active_students"] + 1


# --- POST /admin/seed-demo-data ---
#
# This endpoint shells out to run app/database/seed_synthetic_dataset.py
# as a subprocess against a live, already-running server on
# localhost:8000 — it is fundamentally an integration/ops action, not a
# pure in-process API call, so it cannot be meaningfully exercised
# through the FastAPI TestClient the way every other endpoint in this
# suite is (TestClient never actually binds to a real port for a
# subprocess to connect to). These tests cover what CAN be verified
# without a live server: the auth/permission boundary. End-to-end
# behavior of the endpoint itself is verified manually by running it
# against a real `uvicorn` process (see the project's demo script).


def test_seed_demo_data_requires_admin_auth(client):
    response = client.post("/admin/seed-demo-data")
    assert response.status_code == 401


def test_seed_demo_data_rejects_teacher_token(client, teacher_token):
    response = client.post("/admin/seed-demo-data", headers=auth_header(teacher_token))
    # This codebase's auth convention (see api/deps.py) returns 401 for
    # any role mismatch, not 403.
    assert response.status_code == 401


def test_seed_demo_data_rejects_student_token(client, student_token):
    response = client.post("/admin/seed-demo-data", headers=auth_header(student_token))
    assert response.status_code == 401
