"""Unit tests for the stored verification report endpoint."""
import os
import sys
import uuid

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.database import get_db
from app.core.security import get_current_user
from app.main import app
from app.models.models import DocumentRecord, VerificationCase


@pytest.fixture
async def report_client(db_session, monkeypatch):
    """FastAPI client with DB + auth dependencies overridden."""

    async def override_get_db():
        yield db_session

    async def override_current_user():
        return {"user_id": str(uuid.uuid4()), "role": "officer"}

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = override_current_user

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client

    app.dependency_overrides.clear()


async def test_report_returns_verified_false_when_not_present(report_client, db_session):
    case = VerificationCase(
        case_number="VRX-2026-900002",
        status="in_review",
        risk_level="unknown",
        risk_score=0.0,
    )
    db_session.add(case)
    await db_session.flush()
    doc = DocumentRecord(
        case_id=case.id,
        storage_key="cases/x/y.jpg",
        content_hash=uuid.uuid4().hex,
        mime_type="image/jpeg",
        file_size=10,
    )
    db_session.add(doc)
    await db_session.commit()

    r = await report_client.get(f"/api/v1/verification/{doc.id}/report")
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["verified"] is False
    assert "verification" not in data


async def test_report_returns_stored_report(report_client, db_session):
    case = VerificationCase(
        case_number="VRX-2026-900003",
        status="in_review",
        risk_level="unknown",
        risk_score=0.0,
    )
    db_session.add(case)
    await db_session.flush()
    report = {
        "document_type": "passport",
        "risk": {"score": 0.1, "level": "LOW", "factors": [], "explanation": "ok"},
    }
    doc = DocumentRecord(
        case_id=case.id,
        storage_key="cases/x/y.jpg",
        content_hash=uuid.uuid4().hex,
        mime_type="image/jpeg",
        file_size=10,
        verification_data=report,
    )
    db_session.add(doc)
    await db_session.commit()

    r = await report_client.get(f"/api/v1/verification/{doc.id}/report")
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["verified"] is True
    assert data["verification"]["document_type"] == "passport"
    assert data["verification"]["risk"]["level"] == "LOW"


async def test_report_returns_404_for_unknown_document(report_client):
    r = await report_client.get(
        f"/api/v1/verification/{uuid.uuid4()}/report"
    )
    assert r.status_code == 404
