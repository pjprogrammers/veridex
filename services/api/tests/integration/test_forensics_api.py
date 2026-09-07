"""Integration tests for the modular forensics endpoints (minIO mocked)."""
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


def _document_bytes():
    """A synthetic yet realistic JPEG document (noise-textured field)."""
    rng = np.random.default_rng(2)
    img = np.full((600, 900, 3), 205, dtype=np.uint8)
    noise = rng.integers(-10, 10, (600, 900, 3), dtype=np.int16)
    img = cv2.add(img, noise.astype(np.uint8), dtype=cv2.CV_8U)
    cv2.rectangle(img, (60, 60), (860, 560), (80, 80, 80), 2)
    cv2.putText(img, "DOC AB1234", (120, 200), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (60, 60, 60), 2)
    ok, buf = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 92])
    assert ok
    return buf.tobytes()


@pytest.fixture
async def forensics_client(db_session, monkeypatch):
    async def override_get_db():
        yield db_session

    async def override_current_user():
        uid = os.getenv("TEST_USER_ID", "11111111-1111-1111-1111-111111111111")
        return {"user_id": uid, "role": "officer"}

    keys = {}

    def fake_store_original(data, mime, doc_id, case_id=None, ext="jpg"):
        key = f"documents/{doc_id}/original.{ext}"
        keys[key] = data
        return key

    def fake_load_original(storage_key):
        return keys.get(storage_key, _document_bytes())

    def fake_store_processed(image, doc_id, case_id=None, kind="processed"):
        key = f"documents/{doc_id}/{kind}.jpg"
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
        yield client, keys

    app.dependency_overrides.clear()


async def _upload(client):
    files = {"file": ("doc.jpg", _document_bytes(), "image/jpeg")}
    r = await client.post("/api/v1/documents/upload", files=files)
    assert r.status_code == 201, r.text
    return r.json()["id"]


async def test_forensics_run_returns_structured_result(forensics_client, db_session):
    client, _ = forensics_client
    doc_id = await _upload(client)

    r = await client.post(f"/api/v1/documents/{doc_id}/forensics")
    assert r.status_code == 200, r.text
    body = r.json()

    assert body["document_id"] == doc_id
    # Synthetic JPEG has no editing-software metadata, so no conditional evidence.
    assert body["forensic_status"] == "insufficient_evidence"
    assert body["tampering_score"] is None
    assert body["level"] in {"NONE", "LOW", "MEDIUM", "HIGH"}

    detectors = body["detectors"]
    ids = {d["detector_id"] for d in detectors}
    assert ids == {"ela", "copy_move", "compression", "metadata", "portrait", "text"}
    for d in detectors:
        assert 0.0 <= d["score"] <= 1.0
        assert d["severity"] in {"LOW", "MEDIUM", "HIGH"}
        assert d["description"]
        assert d["detector_status"] in {"production", "conditional", "experimental", "unvalidated"}
        # Cautious framing only — never a forgery verdict.
        assert "forgery" not in d["description"].lower()

    assert isinstance(body["artifact_keys"], dict)
    assert body["artifact_keys"].get("ela:ela_map")
    assert body["artifact_keys"].get("ela:ela_heatmap")


async def test_forensics_persists_and_get_returns_it(forensics_client, db_session):
    client, _ = forensics_client
    doc_id = await _upload(client)

    post_r = await client.post(f"/api/v1/documents/{doc_id}/forensics")
    assert post_r.status_code == 200

    get_r = await client.get(f"/api/v1/documents/{doc_id}/forensics")
    assert get_r.status_code == 200
    body = get_r.json()
    assert body["document_id"] == doc_id
    forensics = body["forensics"]
    assert forensics["tampering_score"] == post_r.json()["tampering_score"]
    assert len(forensics["detectors"]) == 6
    assert "artifact_keys" in forensics


async def test_forensics_get_without_run_returns_404(forensics_client, db_session):
    client, _ = forensics_client
    doc_id = await _upload(client)
    r = await client.get(f"/api/v1/documents/{doc_id}/forensics")
    assert r.status_code == 404


async def test_forensics_unknown_document_returns_404(forensics_client, db_session):
    client, _ = forensics_client
    r = await client.get(f"/api/v1/documents/{uuid.uuid4()}/forensics")
    assert r.status_code == 404
