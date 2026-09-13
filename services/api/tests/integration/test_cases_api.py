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


async def test_new_case_piyush_demo_stores_values_and_anchors_audit(api_client, db_session):
    """A case created with the piyush Aadhaar scenario must persist the actual
    extracted values and anchor a result hash in the audit chain."""
    import uuid

    from sqlalchemy import select

    from app.models.models import AuditLog, DocumentRecord, VerificationCase

    client, headers = api_client
    r = await client.post(
        "/api/v1/cases",
        json={"case_description": "Piyush Aadhaar demo", "scenario": "aadhaar"},
        headers=headers,
    )
    assert r.status_code == 201, r.text
    case_id = r.json()["id"]

    doc = DocumentRecord(
        case_id=uuid.UUID(case_id),
        content_hash="a" * 64,
        mime_type="image/jpeg",
        file_size=1234,
    )
    db_session.add(doc)
    await db_session.commit()
    await db_session.refresh(doc)

    resp = await client.post(
        f"/api/v1/verification/{doc.id}/full?check_registry=true",
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["demo"] is True
    fields = body["verification"]["extracted_fields"]
    assert fields["document_number"] == "5457 0950 4811"
    assert fields["full_name"] == "पीयूष वर्मा"
    assert fields["name_romanized"] == "PIYUSH VERMA"
    assert fields["cid/VID"] == "9103 2996 4131 2258"
    assert body["verification"]["risk"]["level"] == "LOW"

    await db_session.refresh(doc)
    assert doc.document_type == "aadhaar"
    assert doc.extracted_fields["document_number"] == "5457 0950 4811"
    assert doc.verification_data["extracted_fields"]["name_romanized"] == "PIYUSH VERMA"

    case = await db_session.get(VerificationCase, uuid.UUID(case_id))
    assert case.case_metadata["scenario"] == "aadhaar"
    assert len(case.case_metadata["verification_hash"]) == 64
    assert case.document_hash == "a" * 64

    entry = await db_session.scalar(
        select(AuditLog).where(AuditLog.case_id == uuid.UUID(case_id)).order_by(
            AuditLog.id.desc()
        )
    )
    assert entry.action == "verification_completed"
    assert len(entry.payload["verification_hash"]) == 64
    assert entry.payload["extracted_fields"]["document_number"] == "5457 0950 4811"

    chain = await client.get(f"/api/v1/audit/verify/{case_id}", headers=headers)
    assert chain.json()["valid"] is True
