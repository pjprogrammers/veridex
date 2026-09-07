"""Integration tests for the OCR extraction endpoint (MinIO + engine mocked)."""
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
from app.pipeline.ocr import BaseOCREngine, OCRResult


def _png_bytes():
    img = np.full((400, 600, 3), 220, dtype=np.uint8)
    ok, buf = cv2.imencode(".png", img)
    assert ok
    return buf.tobytes()


class _FakeOCREngine(BaseOCREngine):
    """Deterministic OCR engine for testing extraction."""

    name = "baseline"

    def __init__(self, text: str, words: list[dict] | None = None, conf: float = 0.95):
        self._text = text
        self._words = words or []
        self._conf = conf

    def run(self, image: np.ndarray) -> OCRResult:
        return OCRResult(
            full_text=self._text,
            words=[
                w if "confidence" in w else {**w, "confidence": self._conf}
                for w in self._words
            ],
            confidence=self._conf,
            engine=self.name,
        )


@pytest.fixture
async def ocr_client(db_session, monkeypatch):
    async def override_get_db():
        yield db_session

    async def override_current_user():
        uid = os.getenv("TEST_USER_ID", "11111111-1111-1111-1111-111111111111")
        return {"user_id": uid, "role": "officer"}

    # Mock image download so MinIO is never contacted.
    images = {}

    def fake_download_file(bucket, storage_key):
        return images[storage_key]

    import app.routes.ocr as ocr_route
    from app.core import storage as core_storage

    monkeypatch.setattr(ocr_route, "download_file", fake_download_file)
    monkeypatch.setattr(core_storage, "download_file", fake_download_file)

    # Mock the OCR engine factory to return a digestible, deterministic engine.
    engine_holder = {}

    def make_words(words):
        # word: {text, box} — confidence added by engine
        return words

    def fake_get_ocr_engine(client_state=None):
        return client_state

    monkeypatch.setattr(ocr_route, "get_ocr_engine", lambda: engine_holder.get("engine", _FakeOCREngine("")))

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = override_current_user

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield {
            "client": client,
            "images": images,
            "set_engine": lambda eng: engine_holder.update(engine=eng),
            "make_words": make_words,
        }

    app.dependency_overrides.clear()


def _word(text: str, x: int, y: int) -> dict:
    return {
        "text": text,
        "box": [[x, y], [x + 100, y], [x + 100, y + 20], [x, y + 20]],
    }


async def _seed_document(db_session, images, key="documents/test/original.jpg"):
    """Insert a minimal DocumentRecord pointing at a stored image."""
    doc = DocumentRecord(
        id=uuid.uuid4(),
        document_type="passport",
        status="READY",
        original_key=key,
        processed_key=key,
        content_hash="hash-" + uuid.uuid4().hex,
    )
    db_session.add(doc)
    await db_session.commit()
    data = _png_bytes()
    images[key] = data
    return doc


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------

async def test_ocr_extract_happy_path(db_session, ocr_client):
    doc = await _seed_document(db_session, ocr_client["images"])
    words = [
        _word("PASSPORT", 0, 0),
        _word("NO.", 150, 0),
        _word("AB1234567", 300, 0),
        _word("NAME", 0, 40),
        _word("JOHN", 150, 40),
        _word("DOE", 300, 40),
    ]
    ocr_client["set_engine"](_FakeOCREngine("PASSPORT NO. AB1234567\nNAME JOHN DOE", words, conf=0.9))

    r = await ocr_client["client"].post(
        "/api/v1/ocr/v1/extract", json={"document_id": str(doc.id)}
    )
    assert r.status_code == 200, r.text
    data = r.json()
    assert "fields" in data
    assert "raw_text" in data
    assert "processing_time_ms" in data

    by_name = {f["field_name"]: f for f in data["fields"]}
    assert by_name["passport_number"]["value"] == "AB1234567"
    assert by_name["full_name"]["value"] == "JOHN DOE"
    assert by_name["passport_number"]["confidence"] == pytest.approx(0.9, abs=0.01)
    assert by_name["passport_number"]["bbox"]  # boxes preserved


async def test_ocr_results_persisted_to_db(db_session, ocr_client):
    doc = await _seed_document(db_session, ocr_client["images"])
    words = [
        _word("PASSPORT", 0, 0),
        _word("NO.", 150, 0),
        _word("AB1234567", 300, 0),
    ]
    ocr_client["set_engine"](_FakeOCREngine("PASSPORT NO. AB1234567", words, conf=0.85))

    r = await ocr_client["client"].post(
        "/api/v1/ocr/v1/extract", json={"document_id": str(doc.id)}
    )
    assert r.status_code == 200, r.text

    fresh = await db_session.get(DocumentRecord, doc.id)
    assert fresh.ocr_data is not None
    assert fresh.ocr_data["text"] == "PASSPORT NO. AB1234567"
    assert fresh.ocr_extracted_fields is not None
    assert fresh.ocr_extracted_fields["document_type"] == "passport"
    fields = fresh.ocr_extracted_fields["fields"]
    assert fields[0]["field_name"] == "passport_number"
    assert fields[0]["value"] == "AB1234567"


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------

async def test_ocr_missing_document(ocr_client):
    r = await ocr_client["client"].post(
        "/api/v1/ocr/v1/extract",
        json={"document_id": "00000000-0000-0000-0000-000000000000"},
    )
    assert r.status_code == 404


async def test_ocr_invalid_uuid(ocr_client):
    r = await ocr_client["client"].post(
        "/api/v1/ocr/v1/extract", json={"document_id": "not-a-uuid"}
    )
    assert r.status_code == 422


async def test_ocr_no_auth(db_session, ocr_client):
    # Clear the dependency override for the current user to simulate no auth.
    app.dependency_overrides.pop(get_current_user, None)

    doc = await _seed_document(db_session, ocr_client["images"])
    r = await ocr_client["client"].post(
        "/api/v1/ocr/v1/extract", json={"document_id": str(doc.id)}
    )
    assert r.status_code == 401 or r.status_code == 403


async def test_ocr_no_image_available(db_session, ocr_client):
    doc = DocumentRecord(
        id=uuid.uuid4(),
        document_type="passport",
        status="UPLOADED",
        original_key=None,
    )
    db_session.add(doc)
    await db_session.commit()

    r = await ocr_client["client"].post(
        "/api/v1/ocr/v1/extract", json={"document_id": str(doc.id)}
    )
    assert r.status_code == 422
    assert "No image available" in r.json()["detail"]


async def test_ocr_engine_failure_returns_422(ocr_client, db_session):
    doc = await _seed_document(db_session, ocr_client["images"])

    class _FailingEngine(BaseOCREngine):
        name = "failing"

        def run(self, image):
            raise RuntimeError("engine exploded")

    ocr_client["set_engine"](_FailingEngine())
    r = await ocr_client["client"].post(
        "/api/v1/ocr/v1/extract", json={"document_id": str(doc.id)}
    )
    assert r.status_code == 422
    assert "engine failed" in r.json()["detail"]


async def test_ocr_visa_extraction(db_session, ocr_client):
    doc = await _seed_document(db_session, ocr_client["images"])
    doc.document_type = "visa"
    await db_session.commit()

    words = [
        _word("VISA", 0, 0),
        _word("NO.", 150, 0),
        _word("V12345678", 300, 0),
        _word("VALID", 0, 40),
        _word("FROM", 150, 40),
        _word("10-06-2024", 300, 40),
    ]
    ocr_client["set_engine"](_FakeOCREngine("VISA NO. V12345678\nVALID FROM 10-06-2024", words, conf=0.9))

    r = await ocr_client["client"].post(
        "/api/v1/ocr/v1/extract", json={"document_id": str(doc.id)}
    )
    assert r.status_code == 200, r.text
    by_name = {f["field_name"]: f for f in r.json()["fields"]}
    assert by_name["visa_number"]["value"] == "V12345678"
    assert by_name["valid_from"]["value"] == "240610"
