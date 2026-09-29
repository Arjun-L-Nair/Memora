"""
tests/test_auth.py

Covers Phase 16 Section 5 (Authentication and Authorization):
teacher/student/admin login success + failure, invalid/expired tokens,
refresh rotation, and role isolation across all three roles.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from jose import jwt

from app.core.config import settings
from tests.conftest import auth_header


# --- Login success/failure ---


def test_teacher_login_success(client, seeded_teacher):
    response = client.post(
        "/auth/teacher/login",
        json={"email": seeded_teacher.email, "password": "password123"},
    )
    assert response.status_code == 200
    body = response.json()
    assert "access_token" in body and "refresh_token" in body
    assert body["token_type"] == "bearer"


def test_teacher_login_wrong_password(client, seeded_teacher):
    response = client.post(
        "/auth/teacher/login",
        json={"email": seeded_teacher.email, "password": "wrong-password"},
    )
    assert response.status_code == 401


def test_teacher_login_unknown_email(client):
    response = client.post(
        "/auth/teacher/login",
        json={"email": "nobody@test.com", "password": "whatever123"},
    )
    assert response.status_code == 401


def test_student_login_success(client, seeded_student):
    response = client.post(
        "/auth/student/login",
        json={"student_code": seeded_student.student_code, "pin": "1234"},
    )
    assert response.status_code == 200
    assert "access_token" in response.json()


def test_student_login_wrong_pin(client, seeded_student):
    response = client.post(
        "/auth/student/login",
        json={"student_code": seeded_student.student_code, "pin": "9999"},
    )
    assert response.status_code == 401


def test_student_login_pin_must_be_four_digits(client, seeded_student):
    """Validation failure (not auth failure) for a malformed PIN shape."""
    response = client.post(
        "/auth/student/login",
        json={"student_code": seeded_student.student_code, "pin": "12"},
    )
    assert response.status_code == 422


def test_admin_login_success(client, seeded_admin):
    response = client.post(
        "/admin/login",
        json={"email": seeded_admin.email, "password": "password123"},
    )
    assert response.status_code == 200
    assert "access_token" in response.json()


def test_admin_login_wrong_password(client, seeded_admin):
    response = client.post(
        "/admin/login",
        json={"email": seeded_admin.email, "password": "wrong"},
    )
    assert response.status_code == 401


# --- Invalid / expired tokens ---


def test_protected_endpoint_rejects_missing_token(client):
    response = client.get("/students")
    assert response.status_code in (401, 403)


def test_protected_endpoint_rejects_malformed_token(client):
    response = client.get("/students", headers=auth_header("not-a-real-jwt"))
    assert response.status_code == 401


def test_protected_endpoint_rejects_expired_token(client, seeded_teacher):
    """
    Crafts a genuinely expired access token (signed with the real test
    SECRET_KEY, so the signature itself is valid) to verify expiry is
    actually enforced, not just signature validity.
    """
    now = datetime.now(timezone.utc)
    expired_payload = {
        "sub": str(seeded_teacher.id),
        "role": "teacher",
        "type": "access",
        "iat": now - timedelta(minutes=60),
        "exp": now - timedelta(minutes=30),
        "jti": "expired-test-token",
    }
    expired_token = jwt.encode(
        expired_payload,
        settings.SECRET_KEY.get_secret_value(),
        algorithm=settings.JWT_ALGORITHM,
    )
    response = client.get("/students", headers=auth_header(expired_token))
    assert response.status_code == 401


def test_refresh_token_rotation(client, seeded_teacher):
    login = client.post(
        "/auth/teacher/login",
        json={"email": seeded_teacher.email, "password": "password123"},
    )
    original_refresh = login.json()["refresh_token"]

    refreshed = client.post("/auth/refresh", json={"refresh_token": original_refresh})
    assert refreshed.status_code == 200
    new_tokens = refreshed.json()
    assert new_tokens["access_token"] != login.json()["access_token"]
    assert new_tokens["refresh_token"] != original_refresh

    # New access token must actually work against a protected endpoint.
    check = client.get("/students", headers=auth_header(new_tokens["access_token"]))
    assert check.status_code == 200


def test_refresh_rejects_access_token(client, teacher_token):
    """An access token must not be usable as a refresh token."""
    response = client.post("/auth/refresh", json={"refresh_token": teacher_token})
    assert response.status_code == 401


def test_refresh_rejects_invalid_token(client):
    response = client.post("/auth/refresh", json={"refresh_token": "garbage"})
    assert response.status_code == 401


# --- Role isolation ---


def test_student_cannot_access_teacher_endpoint(client, student_token):
    response = client.get("/students", headers=auth_header(student_token))
    assert response.status_code in (401, 403)


def test_student_cannot_access_admin_endpoint(client, student_token):
    response = client.get("/admin/teachers", headers=auth_header(student_token))
    assert response.status_code in (401, 403)


def test_teacher_cannot_access_admin_endpoint(client, teacher_token):
    response = client.get("/admin/teachers", headers=auth_header(teacher_token))
    assert response.status_code in (401, 403)


def test_teacher_cannot_access_student_only_endpoint(client, teacher_token):
    response = client.get("/student-learning/today", headers=auth_header(teacher_token))
    assert response.status_code in (401, 403)


def test_admin_cannot_impersonate_student(client, admin_token):
    """Admin has no route into student-scoped endpoints at all."""
    response = client.get("/student-learning/today", headers=auth_header(admin_token))
    assert response.status_code in (401, 403)
