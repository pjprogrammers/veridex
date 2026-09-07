"""Unit tests for the auth API (login, register, /me)."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.database import get_db
from app.core.security import hash_password
from app.main import app
from app.models.models import Role, User, user_roles


@pytest.fixture
async def auth_client(db_session):
    """FastAPI test client with DB dependency overridden."""

    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    # Seed an OFFICER role and a test user into the in-memory DB
    role = Role(name="OFFICER", description="Test officer role", permissions=["cases:read"])
    db_session.add(role)
    await db_session.flush()

    user = User(
        username="testuser",
        email="testuser@veridex.local",
        hashed_password=hash_password("TestPass123!"),
        full_name="Test User",
        role="officer",
    )
    db_session.add(user)
    await db_session.flush()

    # Assign role
    await db_session.execute(
        user_roles.insert().values(user_id=user.id, role_id=role.id)
    )
    await db_session.commit()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client

    app.dependency_overrides.clear()


async def test_login_success(auth_client):
    r = await auth_client.post(
        "/api/v1/auth/login",
        json={"username": "testuser", "password": "TestPass123!"},
    )
    assert r.status_code == 200, r.text
    data = r.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"


async def test_login_wrong_password(auth_client):
    r = await auth_client.post(
        "/api/v1/auth/login",
        json={"username": "testuser", "password": "WrongPassword!"},
    )
    assert r.status_code == 401
    assert "Invalid credentials" in r.json()["detail"]


async def test_login_nonexistent_user(auth_client):
    r = await auth_client.post(
        "/api/v1/auth/login",
        json={"username": "nobody", "password": "irrelevant"},
    )
    assert r.status_code == 401


async def test_register_then_login(auth_client):
    r = await auth_client.post(
        "/api/v1/auth/register",
        json={
            "username": "newofficer",
            "email": "new@veridex.dev",
            "password": "NewPass123!",
        },
    )
    assert r.status_code == 201, r.text

    # Now login
    r2 = await auth_client.post(
        "/api/v1/auth/login",
        json={"username": "newofficer", "password": "NewPass123!"},
    )
    assert r2.status_code == 200
    assert "access_token" in r2.json()


async def test_register_duplicate_username(auth_client):
    await auth_client.post(
        "/api/v1/auth/register",
        json={
            "username": "dupe_user",
            "email": "dupe@veridex.dev",
            "password": "DupePass123!",
        },
    )
    r = await auth_client.post(
        "/api/v1/auth/register",
        json={
            "username": "dupe_user",
            "email": "dupe2@veridex.dev",
            "password": "DupePass123!",
        },
    )
    assert r.status_code == 409


async def test_me_with_valid_token(auth_client):
    r = await auth_client.post(
        "/api/v1/auth/login",
        json={"username": "testuser", "password": "TestPass123!"},
    )
    token = r.json()["access_token"]
    me = await auth_client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert me.status_code == 200
    assert me.json()["username"] == "testuser"


async def test_me_without_token(auth_client):
    r = await auth_client.get("/api/v1/auth/me")
    assert r.status_code in (401, 403)


async def test_me_with_invalid_token(auth_client):
    r = await auth_client.get(
        "/api/v1/auth/me",
        headers={"Authorization": "Bearer invalid.jwt.token"},
    )
    assert r.status_code == 401
