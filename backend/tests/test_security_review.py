"""
tests/test_security_review.py

Covers Phase 16 Section 18 (Security Review): JWT algorithm/tampering
resistance, sensitive-data exposure, error-message leakage, CORS
enforcement, input validation edge cases, and insecure direct object
reference (IDOR) checks not already covered by the ownership tests in
test_students.py / test_learning_plans.py / test_admin.py.

This is a read-only review + test ticket. No production code was
modified. Findings that are informational (not defects requiring a
fix) are called out in comments and in the ticket report, not silently
"fixed" here.
"""

from __future__ import annotations

import base64
import json

from jose import jwt as jose_jwt

from app.core.config import settings
from tests.conftest import auth_header


# ==========================================================================
# 1. JWT tampering / algorithm-confusion resistance
# ==========================================================================


def test_token_signed_with_wrong_secret_is_rejected(client, seeded_teacher):
    forged = jose_jwt.encode(
        {"sub": str(seeded_teacher.id), "role": "teacher", "type": "access"},
        "wrong-secret-key",
        algorithm="HS256",
    )
    response = client.get("/students", headers=auth_header(forged))
    assert response.status_code == 401


def test_token_signed_with_none_algorithm_is_rejected(client, seeded_teacher):
    """
    The classic 'alg: none' JWT vulnerability: some libraries will
    accept an unsigned token if the caller doesn't pin the expected
    algorithm(s). app.core.security.decode_token() calls
    jwt.decode(..., algorithms=[settings.JWT_ALGORITHM]) — explicitly
    pinned — so this must be rejected.

    python-jose's own encode() refuses to produce an 'alg: none' token
    at all (JWSError: Algorithm none not supported) — which is itself
    a good sign — so the malicious token is constructed manually here
    to simulate what an attacker's own tooling could still produce.
    """
    header = base64.urlsafe_b64encode(b'{"alg":"none","typ":"JWT"}').rstrip(b"=").decode()
    payload = base64.urlsafe_b64encode(
        json.dumps(
            {"sub": str(seeded_teacher.id), "role": "teacher", "type": "access"}
        ).encode()
    ).rstrip(b"=").decode()
    forged = f"{header}.{payload}."  # empty signature, as 'none' alg requires

    response = client.get("/students", headers=auth_header(forged))
    assert response.status_code == 401


def test_token_with_tampered_role_claim_is_rejected(client, seeded_student, seeded_teacher):
    """
    A token correctly signed by the real secret, but with the role
    claim manually changed to escalate privilege, must still fail —
    changing any claim invalidates the signature, since the signature
    covers the whole payload.
    """
    valid_student_token = jose_jwt.encode(
        {
            "sub": str(seeded_student.id),
            "role": "student",
            "type": "access",
            "iat": 0,
            "exp": 9999999999,
        },
        settings.SECRET_KEY.get_secret_value(),
        algorithm=settings.JWT_ALGORITHM,
    )
    # Decode, tamper with role, re-encode WITHOUT re-signing correctly
    # (simulate an attacker editing the payload of a token they don't
    # have the secret for, then just swapping the header/payload but
    # keeping the original signature — this must fail on signature
    # mismatch).
    header_b64, payload_b64, signature_b64 = valid_student_token.split(".")

    payload = json.loads(base64.urlsafe_b64decode(payload_b64 + "=="))
    payload["role"] = "teacher"
    tampered_payload_b64 = (
        base64.urlsafe_b64encode(json.dumps(payload).encode()).rstrip(b"=").decode()
    )
    tampered_token = f"{header_b64}.{tampered_payload_b64}.{signature_b64}"

    response = client.get("/students", headers=auth_header(tampered_token))
    assert response.status_code == 401


def test_refresh_token_cannot_be_used_as_access_token(client, seeded_teacher):
    """A 'type': 'refresh' token must never authenticate a normal request."""
    login = client.post(
        "/auth/teacher/login",
        json={"email": seeded_teacher.email, "password": "password123"},
    )
    refresh_token = login.json()["refresh_token"]
    response = client.get("/students", headers=auth_header(refresh_token))
    assert response.status_code == 401


# ==========================================================================
# 2. Sensitive data never exposed in responses
# ==========================================================================


def test_student_response_never_includes_pin_or_hash(client, teacher_token):
    response = client.post(
        "/students",
        json={"student_code": "SECCHK1", "full_name": "Sec Check", "pin": "1234"},
        headers=auth_header(teacher_token),
    )
    body = response.json()
    serialized = str(body)
    assert "pin_hash" not in serialized
    assert '"pin"' not in serialized
    assert "1234" not in serialized


def test_teacher_response_never_includes_password_or_hash(client, admin_token):
    response = client.post(
        "/admin/teachers",
        json={"full_name": "Sec Teacher", "email": "sec.teacher@test.com", "password": "hunter2"},
        headers=auth_header(admin_token),
    )
    serialized = str(response.json())
    assert "password_hash" not in serialized
    assert "hunter2" not in serialized


def test_admin_response_never_includes_password_hash(client, admin_token, seeded_admin):
    """No admin GET-self endpoint exists, but the login response itself
    must never carry the hash — only tokens."""
    login = client.post(
        "/admin/login", json={"email": seeded_admin.email, "password": "password123"}
    )
    serialized = str(login.json())
    assert "password_hash" not in serialized
    assert "password123" not in serialized


# ==========================================================================
# 3. Error-message leakage
# ==========================================================================


def test_login_failure_message_does_not_reveal_which_field_was_wrong(client, seeded_teacher):
    """
    AuthenticationError is intentionally generic (see auth_service.py
    docstring) so a caller cannot enumerate valid emails by comparing
    'account not found' vs 'wrong password' responses. Confirm both
    failure modes produce an IDENTICAL response body.
    """
    wrong_password = client.post(
        "/auth/teacher/login",
        json={"email": seeded_teacher.email, "password": "wrong"},
    )
    unknown_email = client.post(
        "/auth/teacher/login",
        json={"email": "definitely-not-registered@test.com", "password": "wrong"},
    )
    assert wrong_password.status_code == unknown_email.status_code == 401
    assert wrong_password.json() == unknown_email.json()


def test_404_responses_do_not_distinguish_nonexistent_from_unowned(
    client, teacher_token, second_teacher_token, seeded_student
):
    """
    A teacher probing another teacher's student ID must get the exact
    same response as probing an ID that doesn't exist at all — see
    api/v1/students.py's _STUDENT_NOT_FOUND reuse pattern.
    """
    unowned = client.get(
        f"/students/{seeded_student.id}", headers=auth_header(second_teacher_token)
    )
    nonexistent = client.get("/students/999999999", headers=auth_header(teacher_token))
    assert unowned.status_code == nonexistent.status_code == 404
    assert unowned.json() == nonexistent.json()


def test_unhandled_server_error_does_not_leak_internals(client, admin_token):
    """
    Sanity check on the generic-500 behavior already confirmed live in
    Ticket H for the ML pipeline: FastAPI's default handler must not
    return a stack trace or exception class name in the response body.
    This test uses a malformed-but-plausible request path to probe for
    any accidental debug leakage rather than forcing a real crash.
    """
    # A non-numeric path parameter where an int is expected triggers
    # FastAPI's own validation layer (422), which is safe/expected —
    # included here to confirm even THIS doesn't leak a traceback.
    response = client.get(
        "/students/not-a-number", headers=auth_header(admin_token)
    )
    assert response.status_code in (401, 403, 422)  # admin lacks teacher role -> 401/403 first
    assert "Traceback" not in response.text
    assert "File \"" not in response.text


# ==========================================================================
# 4. CORS enforcement (formalizes the manual check from Ticket A)
# ==========================================================================


def test_cors_allows_configured_frontend_origin(client):
    response = client.options(
        "/students",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert response.headers.get("access-control-allow-origin") == "http://localhost:5173"


def test_cors_rejects_unlisted_origin(client):
    response = client.options(
        "/students",
        headers={
            "Origin": "http://evil.example.com",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert "access-control-allow-origin" not in response.headers


# ==========================================================================
# 5. Input validation edge cases
# ==========================================================================


def test_pin_must_be_exactly_four_digits_not_more(client, teacher_token):
    response = client.post(
        "/students",
        json={"student_code": "TOOLONGPIN", "full_name": "X", "pin": "12345"},
        headers=auth_header(teacher_token),
    )
    assert response.status_code == 422


def test_pin_rejects_non_numeric(client, teacher_token):
    response = client.post(
        "/students",
        json={"student_code": "LETTERPIN", "full_name": "X", "pin": "abcd"},
        headers=auth_header(teacher_token),
    )
    assert response.status_code == 422


def test_email_field_rejects_malformed_email(client):
    response = client.post(
        "/auth/teacher/login",
        json={"email": "not-an-email", "password": "whatever123"},
    )
    assert response.status_code == 422


def test_empty_password_rejected_by_schema(client):
    response = client.post(
        "/auth/teacher/login",
        json={"email": "someone@test.com", "password": ""},
    )
    assert response.status_code == 422


def test_quiz_submit_rejects_empty_answers_list(client, student_token, seeded_session):
    started = client.post(
        f"/quiz-attempts/start/{seeded_session['id']}", headers=auth_header(student_token)
    ).json()
    response = client.post(
        f"/quiz-attempts/{started['id']}/submit",
        json={"answers": []},
        headers=auth_header(student_token),
    )
    assert response.status_code == 422


def test_learning_content_rejects_negative_or_zero_duration(client, teacher_token, seeded_student):
    plan = client.post(
        "/learning-plans",
        json={
            "title": "Duration Check",
            "student_id": seeded_student.id,
            "estimated_duration_minutes": 0,
        },
        headers=auth_header(teacher_token),
    )
    assert plan.status_code == 422


def test_student_code_and_email_do_not_accept_injection_style_strings(client, teacher_token):
    """
    Not a real SQLi test (the ORM parameterizes everything — confirmed
    by code inspection, no raw SQL exists anywhere in the codebase) —
    this simply confirms such input is treated as an ordinary string
    and handled without error, not specially interpreted. Kept within
    the schema's max_length=20 for student_code so this tests string
    handling specifically, not length validation.
    """
    injection_code = "';DROP TABLE x;--"  # 18 chars, fits max_length=20
    response = client.post(
        "/students",
        json={
            "student_code": injection_code,
            "full_name": "Injection Test",
            "pin": "1234",
        },
        headers=auth_header(teacher_token),
    )
    assert response.status_code == 201
    assert response.json()["student_code"] == injection_code

    # Table must still exist and be queryable afterward.
    listed = client.get("/students", headers=auth_header(teacher_token))
    assert listed.status_code == 200
