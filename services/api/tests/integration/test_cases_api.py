"""Integration tests for the case management API (DB-only, no external services)."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.database import get_db
from app.main import app


@pytest.fixture
async def api_client(db_session):
    """FastAPI test client with DB dependency overridden, auth token minted."""

    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    import uuid

    from app.core.security import create_access_token
    token = create_access_token(
        {"sub": str(uuid.uuid4()), "role": "officer"}
    )
    headers = {"Authorization": f"Bearer {token}"}

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client, headers

    app.dependency_overrides.clear()


async def test_create_and_list_case(api_client):
    client, headers = api_client
    r = await client.post(
        "/api/v1/cases",
        json={"case_description": "Synthetic traveler at border checkpoint"},
        headers=headers,
    )
    assert r.status_code == 201, r.text
    data = r.json()
    assert data["case_number"].startswith("VRX-")
    assert data["status"] == "in_review"

    lis = await client.get("/api/v1/cases", headers=headers)
    assert lis.status_code == 200
    assert lis.json()["total"] >= 1


async def test_update_case_status_with_audit(api_client):
    client, headers = api_client
    r = await client.post("/api/v1/cases", json={}, headers=headers)
    case_id = r.json()["id"]

    # Invalid status rejected
    bad = await client.patch(
        f"/api/v1/cases/{case_id}/status", json={"status": "not_a_status"}, headers=headers
    )
    assert bad.status_code == 422

    # Valid transition
    ok = await client.patch(
        f"/api/v1/cases/{case_id}/status", json={"status": "flagged"}, headers=headers
    )
    assert ok.status_code == 200
    assert ok.json()["status"] == "flagged"

    # Audit entries should exist for create + status change
    audit = await client.get(f"/api/v1/audit?case_id={case_id}", headers=headers)
    assert audit.status_code == 200
    actions = [e["action"] for e in audit.json()]
    assert "case_created" in actions
    assert "case_status_changed" in actions


async def test_audit_chain_verify_endpoint(api_client):
    client, headers = api_client
    r = await client.post("/api/v1/cases", json={}, headers=headers)
    case_id = r.json()["id"]
    await client.patch(
        f"/api/v1/cases/{case_id}/status", json={"status": "cleared"}, headers=headers
    )

    verify = await client.get(f"/api/v1/audit/verify/{case_id}", headers=headers)
    assert verify.status_code == 200
    body = verify.json()
    assert body["valid"] is True
    assert body["total_entries"] >= 2


async def test_delete_case_requires_admin(api_client):
    client, headers = api_client
    r = await client.post("/api/v1/cases", json={}, headers=headers)
    case_id = r.json()["id"]

    resp = await client.delete(f"/api/v1/cases/{case_id}", headers=headers)
    assert resp.status_code == 403  # officer cannot delete


async def test_case_not_found(api_client):
    client, headers = api_client
    import uuid
    resp = await client.get(f"/api/v1/cases/{uuid.uuid4()}", headers=headers)
    assert resp.status_code == 404
