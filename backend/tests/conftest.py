"""
tests/conftest.py

Shared pytest fixtures for the Memora backend test suite
(Phase 16, Ticket G).

Design:
    - Uses a dedicated file-based SQLite test database
      (`test_memora.db`), never the real dev `memora.db`. The
      file is created fresh (all tables dropped + recreated) at the
      start of the test session and removed at the end.
    - Overrides the app's `get_db` FastAPI dependency to use this test
      database's session factory instead of the production one — no
      application code is touched to make this work.
    - A file-based (not in-memory) SQLite DB is used deliberately: the
      app's `connect_args={"check_same_thread": False}` pattern and
      real multi-request behavior are best exercised against something
      closer to how SQLite actually behaves in this app, and it also
      lets a failed test run be inspected afterward if needed.
"""

from __future__ import annotations

import os
from collections.abc import Generator

TEST_DB_PATH = os.path.join(os.path.dirname(__file__), "test_memora.db")
TEST_DATABASE_URL = f"sqlite:///{TEST_DB_PATH}"

# Point the app at the test database BEFORE importing ANYTHING that
# reads settings.DATABASE_URL at import time — this must run before
# even `app.core.security`, since that module imports
# `app.core.config.settings` at its own module level (which
# instantiates the settings singleton once, from whatever the
# environment looked like at that moment). Getting this ordering wrong
# is exactly the kind of bug that stays invisible when
# settings.DATABASE_URL's default happens to be SQLite (no external
# service required either way) and only surfaces once the default
# becomes something like PostgreSQL that actually requires a running
# service/driver — which is what happened here.
os.environ["DATABASE_URL"] = TEST_DATABASE_URL
os.environ.setdefault("SECRET_KEY", "test-secret-key-not-for-production-use-only")
os.environ.setdefault("ENVIRONMENT", "testing")

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.security import hash_password, hash_pin

from app.database import get_db  # noqa: E402
from app.database.base import Base  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Admin, Student, Teacher  # noqa: E402

test_engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
)
TestSessionLocal = sessionmaker(bind=test_engine, autoflush=False, autocommit=False, expire_on_commit=False)


@pytest.fixture(scope="session", autouse=True)
def _test_database():
    """Fresh schema for the whole test session; removed afterward."""
    Base.metadata.drop_all(bind=test_engine)
    Base.metadata.create_all(bind=test_engine)
    yield
    if os.path.exists(TEST_DB_PATH):
        os.remove(TEST_DB_PATH)


@pytest.fixture(autouse=True)
def _clean_tables():
    """
    Truncates every table before each test, so tests don't leak state
    into one another (e.g. two tests both creating a teacher with the
    same email). Schema itself is created once per session by
    `_test_database`; this only clears rows.
    """
    with test_engine.begin() as connection:
        for table in reversed(Base.metadata.sorted_tables):
            connection.execute(table.delete())
    yield


@pytest.fixture(autouse=True)
def _override_get_db():
    def _get_test_db() -> Generator:
        db = TestSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = _get_test_db
    yield
    app.dependency_overrides.clear()


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


@pytest.fixture
def db_session():
    session = TestSessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def seeded_teacher(db_session):
    """A teacher with a known email/password, inserted directly."""
    teacher = Teacher(
        full_name="Test Teacher",
        email="pytest.teacher@test.com",
        password_hash=hash_password("password123"),
        is_active=True,
    )
    db_session.add(teacher)
    db_session.commit()
    db_session.refresh(teacher)
    return teacher


@pytest.fixture
def seeded_second_teacher(db_session):
    """A second, distinct teacher — used for cross-owner isolation tests."""
    teacher = Teacher(
        full_name="Other Teacher",
        email="pytest.teacher2@test.com",
        password_hash=hash_password("password123"),
        is_active=True,
    )
    db_session.add(teacher)
    db_session.commit()
    db_session.refresh(teacher)
    return teacher


@pytest.fixture
def seeded_student(db_session, seeded_teacher):
    """A student owned by `seeded_teacher`, known PIN."""
    student = Student(
        student_code="PYTEST01",
        full_name="Pytest Student",
        pin_hash=hash_pin("1234"),
        teacher_id=seeded_teacher.id,
        current_difficulty_level="Beginner",
        is_active=True,
    )
    db_session.add(student)
    db_session.commit()
    db_session.refresh(student)
    return student


@pytest.fixture
def seeded_admin(db_session):
    admin = Admin(
        full_name="Test Admin",
        email="pytest.admin@test.com",
        password_hash=hash_password("password123"),
    )
    db_session.add(admin)
    db_session.commit()
    db_session.refresh(admin)
    return admin


@pytest.fixture
def teacher_token(client: TestClient, seeded_teacher) -> str:
    response = client.post(
        "/auth/teacher/login",
        json={"email": seeded_teacher.email, "password": "password123"},
    )
    assert response.status_code == 200
    return response.json()["access_token"]


@pytest.fixture
def second_teacher_token(client: TestClient, seeded_second_teacher) -> str:
    response = client.post(
        "/auth/teacher/login",
        json={"email": seeded_second_teacher.email, "password": "password123"},
    )
    assert response.status_code == 200
    return response.json()["access_token"]


@pytest.fixture
def student_token(client: TestClient, seeded_student) -> str:
    response = client.post(
        "/auth/student/login",
        json={"student_code": seeded_student.student_code, "pin": "1234"},
    )
    assert response.status_code == 200
    return response.json()["access_token"]


@pytest.fixture
def admin_token(client: TestClient, seeded_admin) -> str:
    response = client.post(
        "/admin/login",
        json={"email": seeded_admin.email, "password": "password123"},
    )
    assert response.status_code == 200
    return response.json()["access_token"]


def auth_header(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def seeded_session(client: TestClient, teacher_token: str, seeded_student):
    """
    A fully assembled learning plan -> content -> session chain, created
    through the real HTTP API (not inserted directly), so these tests
    also incidentally exercise the teacher-side creation endpoints.
    Returns the session dict (as the API returns it).
    """
    plan = client.post(
        "/learning-plans",
        json={"title": "Fixture Plan", "student_id": seeded_student.id},
        headers=auth_header(teacher_token),
    ).json()

    content = client.post(
        "/learning-content",
        json={
            "title": "Fixture Lesson",
            "body": "Fixture lesson body.",
            "difficulty_level": "Beginner",
            "learning_plan_id": plan["id"],
        },
        headers=auth_header(teacher_token),
    ).json()

    session = client.post(
        "/learning-sessions",
        json={
            "student_id": seeded_student.id,
            "learning_plan_id": plan["id"],
            "learning_content_id": content["id"],
        },
        headers=auth_header(teacher_token),
    ).json()

    return session
