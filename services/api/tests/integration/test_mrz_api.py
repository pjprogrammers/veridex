"""Integration tests for the MRZ extraction endpoint (minIO mocked)."""
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
from app.pipeline.ocr import OCRResult


def _passport_bytes():
    img = np.full((600, 900, 3), 230, dtype=np.uint8)
    cv2.rectangle(img, (60, 60), (860, 560), (180, 180, 180), -1)
    ok, buf = cv2.imencode(".png", img)
    assert ok
    return buf.tobytes()


def _mrz_words(line, y, left=120, char_w=12):
    """Split an MRZ line into tightly-packed word boxes."""
    chunks = [line[i : i + 11] for i in range(0, len(line), 11)]
    words = []
    x = left
    for ch in chunks:
        w = len(ch) * char_w
        words.append(
            {
                "text": ch,
                "confidence": 0.98,
                "box": [
                    [x, y - 7],
                    [x + w, y - 7],
                    [x + w, y + 7],
                    [x, y + 7],
                ],
            }
        )
        x += w
    return words


def _valid_td3_words():
    line1 = TEST_LINE1
    line2 = TEST_LINE2
    return _mrz_words(line1, 520) + _mrz_words(line2, 545)


@pytest.fixture
async def mrz_client(db_session, monkeypatch):
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
        return keys.get(storage_key, _passport_bytes())

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
        yield client

    app.dependency_overrides.clear()


def _make_fake_engine(words):
    class FakeEngine:
        name = "fake"
        def run(self, image):
            text = "\n".join(w["text"] for w in words)
            return OCRResult(full_text=text, words=words, confidence=0.98, engine="fake")
    return FakeEngine()


TEST_LINE2 = "L898902C<3UTO6908061F9406236ZE1842260B<<<<2<"
TEST_LINE1 = "P<UTOERIKSSON<<ANNA<MARIA<<<<<<<<<<<<<<<<<<<"


async def _upload(client, name="passport.png"):
    files = {"file": (name, _passport_bytes(), "image/png")}
    r = await client.post("/api/v1/documents/upload", files=files)
    assert r.status_code == 201, r.text
    return r.json()["id"]


async def test_mrz_extract_returns_parsed_fields(mrz_client, db_session, monkeypatch):
    from app.pipeline import ocr as ocr_mod
    monkeypatch.setattr(ocr_mod, "get_ocr_engine", lambda: _make_fake_engine(_valid_td3_words()))
    doc_id = await _upload(mrz_client)
    # Set mime/keys so load_original resolves and mrz detection can run.
    doc = await db_session.get(DocumentRecord, uuid.UUID(doc_id))
    doc.processed_key = f"documents/{doc_id}/processed.jpg"
    doc.original_key = f"documents/{doc_id}/original.jpg"
    await db_session.commit()

    r = await mrz_client.post(f"/api/v1/documents/{doc_id}/mrz")
    assert r.status_code == 200, r.text
    data = r.json()
    mrz = data["mrz"]
    assert mrz["mrz_detected"] is True
    assert mrz["mrz_valid"] is True
    assert mrz["parsed_fields"]["surname"] == "ERIKSSON"
    assert mrz["parsed_fields"]["given_names"] == "ANNA MARIA"
    assert mrz["check_digits"]["passport_number"] is True
    assert mrz["check_digits"]["date_of_birth"] is True
    assert mrz["check_digits"]["expiry_date"] is True


async def test_mrz_visual_comparison_produced(mrz_client, db_session, monkeypatch):
    from app.pipeline import ocr as ocr_mod
    from app.pipeline.ocr import OCRResult

    # Provide matching visual fields so the comparison runs.
    class FakeEngine:
        name = "fake"
        def run(self, image):
            return OCRResult(
                full_text="\n".join(w["text"] for w in _valid_td3_words()),
                words=_valid_td3_words(), confidence=0.98, engine="fake")

    monkeypatch.setattr(ocr_mod, "get_ocr_engine", lambda: FakeEngine())
    doc_id = await _upload(mrz_client)
    doc = await db_session.get(DocumentRecord, uuid.UUID(doc_id))
    doc.processed_key = f"documents/{doc_id}/processed.jpg"
    doc.original_key = f"documents/{doc_id}/original.jpg"
    doc.classification_data = {"document_type": "passport"}
    doc.ocr_extracted_fields = {
        "passport_number": {"value": "L898902C"},
        "full_name": {"value": "ERIKSSON ANNA MARIA"},
        "date_of_birth": {"value": "690806"},
        "nationality": {"value": "UTO"},
        "date_of_expiry": {"value": "940623"},
    }
    await db_session.commit()

    r = await mrz_client.post(f"/api/v1/documents/{doc_id}/mrz")
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["comparison"] is not None
    assert data["comparison"]["severity"] == "NONE"
    assert all(c["verdict"] == "MATCH" for c in data["comparison"]["comparisons"])


async def test_mrz_rejects_pdf(mrz_client, db_session):
    files = {"file": ("doc.pdf", b"%PDF-1.4 fake", "application/pdf")}
    r = await mrz_client.post("/api/v1/documents/upload", files=files)
    assert r.status_code == 201
    doc_id = r.json()["id"]
    resp = await mrz_client.post(f"/api/v1/documents/{doc_id}/mrz")
    assert resp.status_code == 422
    assert "only supported for image" in resp.json()["detail"]


async def test_mrz_not_detected_when_no_dense_rows(mrz_client, db_session, monkeypatch):
    from app.pipeline import ocr as ocr_mod
    words = [
        {"text": "PASSPORT", "confidence": 0.9, "box": [[100, 50], [200, 50], [200, 64], [100, 64]]},
        {"text": "NAME", "confidence": 0.9, "box": [[100, 90], [180, 90], [180, 104], [100, 104]]},
    ]
    monkeypatch.setattr(ocr_mod, "get_ocr_engine", lambda: _make_fake_engine(words))
    doc_id = await _upload(mrz_client)
    doc = await db_session.get(DocumentRecord, uuid.UUID(doc_id))
    doc.processed_key = f"documents/{doc_id}/processed.jpg"
    doc.original_key = f"documents/{doc_id}/original.jpg"
    await db_session.commit()

    r = await mrz_client.post(f"/api/v1/documents/{doc_id}/mrz")
    assert r.status_code == 200, r.text
    assert r.json()["mrz"]["mrz_detected"] is False


async def test_mrz_mismatch_flagged_but_not_forgery(mrz_client, db_session, monkeypatch):
    """MRZ mismatch is surfaced with HIGH severity but is NOT treated as forgery."""
    from app.pipeline import ocr as ocr_mod
    from app.pipeline.ocr import OCRResult

    class FakeEngine:
        name = "fake"
        def run(self, image):
            return OCRResult(
                full_text="\n".join(w["text"] for w in _valid_td3_words()),
                words=_valid_td3_words(), confidence=0.98, engine="fake")

    monkeypatch.setattr(ocr_mod, "get_ocr_engine", lambda: FakeEngine())
    doc_id = await _upload(mrz_client)
    doc = await db_session.get(DocumentRecord, uuid.UUID(doc_id))
    doc.processed_key = f"documents/{doc_id}/processed.jpg"
    doc.original_key = f"documents/{doc_id}/original.jpg"
    doc.classification_data = {"document_type": "passport"}
    # Visual passport number deliberately differs from the MRZ value (L898902C).
    doc.ocr_extracted_fields = {
        "passport_number": {"value": "L898902X"},
        "full_name": {"value": "ERIKSSON ANNA MARIA"},
        "date_of_birth": {"value": "690806"},
        "nationality": {"value": "UTO"},
        "date_of_expiry": {"value": "940623"},
    }
    await db_session.commit()

    r = await mrz_client.post(f"/api/v1/documents/{doc_id}/mrz")
    assert r.status_code == 200, r.text
    data = r.json()

    # The mismatch is surfaced: comparison runs and flags the passport number.
    assert data["comparison"] is not None
    by_field = {c["field_name"]: c for c in data["comparison"]["comparisons"]}
    assert by_field["passport_number"]["verdict"] == "MISMATCH"
    assert data["comparison"]["severity"] == "HIGH"

    # The MRZ itself is valid/self-consistent — only the visual view disagrees.
    assert data["mrz"]["mrz_detected"] is True
    assert data["mrz"]["mrz_valid"] is True
    assert data["mrz"]["parsed_fields"]["passport_number"].rstrip("<") == "L898902C"

    # Mismatch alone is surfaced for review but NEVER asserted as forgery: the
    # response carries no forgery verdict and the document status is unchanged.
    assert "forgery" not in data
    assert "forgeryVerdict" not in data
    refreshed = await db_session.get(DocumentRecord, uuid.UUID(doc_id))
    assert refreshed.status not in {"FORGED", "REJECTED", "FAILED"}
