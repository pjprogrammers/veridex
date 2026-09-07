"""Integration tests for the document ingestion API (MinIO mocked)."""
import os
import sys
import uuid

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import cv2
import numpy as np
import pytest
from httpx import ASGITransport, AsyncClient

from app.core.database import get_db
from app.core.security import get_current_user
from app.main import app
from app.models.models import DocumentRecord


def _png_bytes():
    img = np.full((400, 600, 3), 220, dtype=np.uint8)
    cv2.rectangle(img, (30, 30), (570, 370), (180, 180, 180), -1)
    for y in range(300, 360, 20):
        cv2.rectangle(img, (50, y), (550, y + 10), (20, 20, 20), -1)
    ok, buf = cv2.imencode(".png", img)
    assert ok
    return buf.tobytes()


@pytest.fixture
async def doc_client(db_session, monkeypatch):
    async def override_get_db():
        yield db_session

    _default_user = "11111111-1111-1111-1111-111111111111"

    async def override_current_user():
        return {
            "user_id": os.getenv("TEST_USER_ID", _default_user),
            "role": "officer",
        }

    # Mock storage so MinIO is never contacted.
    keys = {}

    def fake_store_original(data, mime, doc_id, case_id=None, ext="jpg"):
        prefix = f"cases/{case_id}" if case_id else "documents"
        key = f"{prefix}/{doc_id}/original.{ext}"
        keys[key] = data
        return key

    def fake_load_original(storage_key):
        return keys[storage_key]

    def fake_store_processed(image, doc_id, case_id=None, kind="processed"):
        prefix = f"cases/{case_id}" if case_id else "documents"
        key = f"{prefix}/{doc_id}/{kind}.jpg"
        keys[key] = image
        return key

    import app.routes.documents as doc_routes
    from app.services import ingestion

    monkeypatch.setattr(doc_routes, "store_original", fake_store_original)
    monkeypatch.setattr(doc_routes, "load_original", fake_load_original)
    monkeypatch.setattr(doc_routes, "store_processed", fake_store_processed)
    monkeypatch.setattr(ingestion, "store_original", fake_store_original)
    monkeypatch.setattr(ingestion, "load_original", fake_load_original)
    monkeypatch.setattr(ingestion, "store_processed", fake_store_processed)

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = override_current_user

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client

    app.dependency_overrides.clear()


async def test_upload_png_stores_and_returns_metadata(doc_client, db_session):
    files = {"file": ("id_front.png", _png_bytes(), "image/png")}
    r = await doc_client.post("/api/v1/documents/upload", files=files)
    assert r.status_code == 201, r.text
    data = r.json()
    assert data["status"] == "VALIDATING"
    assert data["mime_type"] == "image/png"
    assert data["original_filename"] == "id_front.png"
    assert data["file_size"] > 0
    assert data["content_hash"]
    assert data["original_key"]

    doc = await db_session.get(DocumentRecord, uuid.UUID(data["id"]))
    assert doc is not None
    assert doc.status == "VALIDATING"


async def test_upload_rejects_unsupported_type(doc_client):
    files = {"file": ("x.gif", b"GIF89a" + b"\x00" * 10, "image/gif")}
    r = await doc_client.post("/api/v1/documents/upload", files=files)
    assert r.status_code == 415


async def test_upload_rejects_corrupt_image(doc_client):
    files = {"file": ("broken.jpg", b"garbage non-image data", "image/jpeg")}
    r = await doc_client.post("/api/v1/documents/upload", files=files)
    assert r.status_code == 400
    assert "not a valid image" in r.json()["detail"]


async def test_upload_duplicate_hash_conflict(doc_client):
    payload = _png_bytes()
    files = {"file": ("a.png", payload, "image/png")}
    r1 = await doc_client.post("/api/v1/documents/upload", files=files)
    assert r1.status_code == 201
    r2 = await doc_client.post("/api/v1/documents/upload", files=files)
    assert r2.status_code == 409


async def test_preprocess_then_fetch_ready_document(doc_client, db_session):
    files = {"file": ("doc.png", _png_bytes(), "image/png")}
    r = await doc_client.post("/api/v1/documents/upload", files=files)
    doc_id = r.json()["id"]

    p = await doc_client.post(f"/api/v1/documents/{doc_id}/preprocess")
    assert p.status_code == 200, p.text
    pdata = p.json()
    assert pdata["status"] == "READY"
    assert pdata["processed_key"]
    assert pdata["preview_key"]
    meta = pdata["preprocess"]
    assert meta["width"] > 0
    assert meta["height"] > 0
    assert "rotation" in meta
    assert "quality_score" in meta
    assert "blur_score" in meta
    assert "brightness_score" in meta
    assert "document_boundary_confidence" in meta

    g = await doc_client.get(f"/api/v1/documents/{doc_id}")
    assert g.status_code == 200
    assert g.json()["status"] == "READY"
    assert g.json()["preprocess"]["quality_score"] > 0


async def test_preprocess_rejects_pdf(doc_client, db_session):
    files = {"file": ("doc.pdf", b"%PDF-1.4 fake", "application/pdf")}
    r = await doc_client.post("/api/v1/documents/upload", files=files)
    assert r.status_code == 201
    doc_id = r.json()["id"]
    p = await doc_client.post(f"/api/v1/documents/{doc_id}/preprocess")
    assert p.status_code == 422
    assert "only supported for image" in p.json()["detail"]


async def test_get_unknown_document_404(doc_client):
    r = await doc_client.get("/api/v1/documents/00000000-0000-0000-0000-000000000000")
    assert r.status_code == 404


# ---------------------------------------------------------------------------
# Phase 4 — Document classification tests
# ---------------------------------------------------------------------------


def _passport_bytes():
    """Synthetic passport-like image (1.25:1 aspect ratio, MRZ zone, header)."""
    w, h = 500, 400
    img = np.full((h, w, 3), 240, dtype=np.uint8)
    cv2.putText(img, "PASSPORT", (50, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (10, 10, 10), 2, cv2.LINE_AA)
    for y in range(int(h * 0.78), h - 15, 18):
        cv2.rectangle(img, (30, y), (w - 30, y + 10), (20, 20, 20), -1)
    ok, buf = cv2.imencode(".png", img)
    assert ok
    return buf.tobytes()


def _unknown_bytes():
    """Plain bright image with no document structure."""
    img = np.full((400, 400, 3), 230, dtype=np.uint8)
    ok, buf = cv2.imencode(".png", img)
    assert ok
    return buf.tobytes()


async def test_classify_passport_document(doc_client, db_session):
    """Upload a passport-like image and classify it."""
    files = {"file": ("passport.png", _passport_bytes(), "image/png")}
    r = await doc_client.post("/api/v1/documents/upload", files=files)
    assert r.status_code == 201, r.text
    doc_id = r.json()["id"]

    c = await doc_client.post(f"/api/v1/documents/{doc_id}/classify")
    assert c.status_code == 200, c.text
    data = c.json()
    assert data["status"] == "READY"
    assert data["document_type"] == "passport"
    assert data["classification"]["document_type"] == "passport"
    assert data["classification"]["confidence"] > 0.0
    assert data["classification"]["method"] == "heuristic"

    # Verify DB state.
    doc = await db_session.get(DocumentRecord, uuid.UUID(doc_id))
    assert doc is not None
    assert doc.document_type == "passport"
    assert doc.classification_data is not None


async def test_classify_unknown_document(doc_client, db_session):
    """Upload a square noise image — should classify as unknown."""
    files = {"file": ("unknown.png", _unknown_bytes(), "image/png")}
    r = await doc_client.post("/api/v1/documents/upload", files=files)
    assert r.status_code == 201, r.text
    doc_id = r.json()["id"]

    c = await doc_client.post(f"/api/v1/documents/{doc_id}/classify")
    assert c.status_code == 200, c.text
    data = c.json()
    assert data["document_type"] == "unknown"
    assert data["classification"]["document_type"] == "unknown"


async def test_classify_rejects_pdf(doc_client, db_session):
    files = {"file": ("doc.pdf", b"%PDF-1.4 fake", "application/pdf")}
    r = await doc_client.post("/api/v1/documents/upload", files=files)
    assert r.status_code == 201
    doc_id = r.json()["id"]
    c = await doc_client.post(f"/api/v1/documents/{doc_id}/classify")
    assert c.status_code == 422
    assert "only supported for image" in c.json()["detail"]
