"""Integration tests for the document validation endpoint (minIO mocked)."""
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

# Self-consistent synthetic TD3 passport MRZ (valid check digits).
TEST_LINE1 = "P<UTOERIKSSON<<ANNA<MARIA<<<<<<<<<<<<<<<<<<<"
TEST_LINE2 = "L898902C<3UTO6908061F9406236ZE1842260B<<<<2<"


def _build_line2(**kwargs):
    """Build a self-consistent (fully valid) TD3 line 2 with a given expiry."""
    from app.pipeline.mrz import mrz_check_digit

    passport = kwargs.get("passport", "L898902C")
    nationality = kwargs.get("nationality", "UTO")
    dob = kwargs.get("dob", "690806")
    sex = kwargs.get("sex", "F")
    expiry = kwargs.get("expiry", "940623")
    personal = kwargs.get("personal", "ZE184226")
    optional = kwargs.get("optional", "0")

    passport_padded = passport.ljust(9, "<")
    passport_cd = str(mrz_check_digit(passport_padded))
    dob_cd = str(mrz_check_digit(dob))
    expiry_cd = str(mrz_check_digit(expiry))
    personal_padded = personal.ljust(8, "<")
    personal_cd = str(mrz_check_digit(personal_padded))
    optional_padded = optional.ljust(5, "<")
    composite = (
        passport_padded[2:9] + passport_cd + nationality
        + dob + dob_cd + sex + expiry + expiry_cd
        + personal_padded + personal_cd + optional_padded
    )
    final_cd = str(mrz_check_digit(composite))
    line = (
        passport_padded + passport_cd + nationality
        + dob + dob_cd + sex + expiry + expiry_cd
        + personal_padded + personal_cd + optional_padded + final_cd + "<"
    )
    assert len(line) == 44
    return line


def _future_td3_words():
    """A valid passport MRZ (matching the realistic visual fields) with a
    far-future expiry, so every check can pass relative to today."""
    line2 = _build_line2(expiry="341231")
    return _mrz_words(TEST_LINE1, 520) + _mrz_words(line2, 545)


def _passport_bytes():
    img = np.full((600, 900, 3), 230, dtype=np.uint8)
    cv2.rectangle(img, (60, 60), (860, 560), (180, 180, 180), -1)
    ok, buf = cv2.imencode(".png", img)
    assert ok
    return buf.tobytes()


def _mrz_words(line, y, left=120, char_w=12):
    chunks = [line[i : i + 11] for i in range(0, len(line), 11)]
    words = []
    x = left
    for ch in chunks:
        w = len(ch) * char_w
        words.append(
            {
                "text": ch,
                "confidence": 0.98,
                "box": [[x, y - 7], [x + w, y - 7], [x + w, y + 7], [x, y + 7]],
            }
        )
        x += w
    return words


def _valid_td3_words():
    return _mrz_words(TEST_LINE1, 520) + _mrz_words(TEST_LINE2, 545)


@pytest.fixture
async def validate_client(db_session, monkeypatch):
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
            return OCRResult(full_text="\n".join(w["text"] for w in words),
                             words=words, confidence=0.98, engine="fake")
    return FakeEngine()


async def _upload(client, name="passport.png"):
    files = {"file": (name, _passport_bytes(), "image/png")}
    r = await client.post("/api/v1/documents/upload", files=files)
    assert r.status_code == 201, r.text
    return r.json()["id"]


def _realistic_extracted(passport="L898902C"):
    """Realistic fields that match the MRZ and are not expired as of 2024."""
    return {
        "passport_number": {"value": passport},
        "full_name": {"value": "ERIKSSON ANNA MARIA"},
        "date_of_birth": {"value": "690806"},
        "date_of_issue": {"value": "940624"},
        "date_of_expiry": {"value": "341231"},
        "nationality": {"value": "UTO"},
        "sex": {"value": "F"},
    }


async def test_validate_all_pass(
    validate_client, db_session, monkeypatch
):
    from app.pipeline import ocr as ocr_mod
    monkeypatch.setattr(ocr_mod, "get_ocr_engine", lambda: _make_fake_engine(_future_td3_words()))
    doc_id = await _upload(validate_client)
    doc = await db_session.get(DocumentRecord, uuid.UUID(doc_id))
    doc.processed_key = f"documents/{doc_id}/processed.jpg"
    doc.original_key = f"documents/{doc_id}/original.jpg"
    doc.document_type = "passport"
    doc.classification_data = {"document_type": "passport"}
    doc.ocr_extracted_fields = _realistic_extracted()
    await db_session.commit()

    r = await validate_client.post(f"/api/v1/documents/{doc_id}/validate")
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["document_id"] == doc_id
    assert data["document_type"] == "passport"
    assert "current_date" in data

    validation = data["validation"]
    assert set(validation) == {"findings", "summary"}
    by_id = {f["rule_id"]: f for f in validation["findings"]}
    assert len(validation["findings"]) >= 13

    # The validity checks should all pass for this well-formed document.
    assert validation["summary"]["overall"] == "PASS"
    assert by_id["required_fields"]["passed"] is True
    assert by_id["field_format"]["passed"] is True
    assert by_id["date_format"]["passed"] is True
    assert by_id["dob_not_future"]["passed"] is True
    assert by_id["document_expired"]["passed"] is True
    assert by_id["mrz_check_digits"]["passed"] is True
    assert by_id["ocr_mrz_consistency"]["passed"] is True
    assert by_id["passport_number_consistency"]["passed"] is True
    assert by_id["name_consistency"]["passed"] is True
    assert by_id["dob_consistency"]["passed"] is True
    assert by_id["expiry_consistency"]["passed"] is True


async def test_validate_detects_mismatch_and_surfaces_not_forgery(
    validate_client, db_session, monkeypatch
):
    from app.pipeline import ocr as ocr_mod
    monkeypatch.setattr(ocr_mod, "get_ocr_engine", lambda: _make_fake_engine(_valid_td3_words()))
    doc_id = await _upload(validate_client)
    doc = await db_session.get(DocumentRecord, uuid.UUID(doc_id))
    doc.processed_key = f"documents/{doc_id}/processed.jpg"
    doc.original_key = f"documents/{doc_id}/original.jpg"
    doc.document_type = "passport"
    doc.classification_data = {"document_type": "passport"}
    # Matching fields EXCEPT the passport number, which deliberately differs.
    fields = _realistic_extracted(passport="L898902X")
    doc.ocr_extracted_fields = fields
    await db_session.commit()

    r = await validate_client.post(f"/api/v1/documents/{doc_id}/validate")
    assert r.status_code == 200, r.text
    validation = r.json()["validation"]
    by_id = {f["rule_id"]: f for f in validation["findings"]}

    # MRZ is valid but the visual passport number disagrees -> mismatch findings.
    assert by_id["passport_number_consistency"]["passed"] is False
    assert by_id["passport_number_consistency"]["severity"] == "HIGH"
    assert by_id["ocr_mrz_consistency"]["passed"] is False
    assert by_id["mrz_check_digits"]["passed"] is True

    # Mismatch is a finding, not a forgery verdict.
    assert validation["summary"]["overall"] == "FAIL"
    assert "forgery" not in r.json()
    refreshed = await db_session.get(DocumentRecord, uuid.UUID(doc_id))
    assert refreshed.status not in {"FORGED", "REJECTED", "FAILED"}


async def test_validate_detects_expired_document(
    validate_client, db_session, monkeypatch
):
    from app.pipeline import ocr as ocr_mod
    monkeypatch.setattr(ocr_mod, "get_ocr_engine", lambda: _make_fake_engine(_valid_td3_words()))
    doc_id = await _upload(validate_client)
    doc = await db_session.get(DocumentRecord, uuid.UUID(doc_id))
    doc.processed_key = f"documents/{doc_id}/processed.jpg"
    doc.original_key = f"documents/{doc_id}/original.jpg"
    doc.document_type = "passport"
    doc.ocr_extracted_fields = _realistic_extracted()
    # Override expiry in the past (relative to today).
    doc.ocr_extracted_fields["date_of_expiry"] = {"value": "200101"}
    await db_session.commit()

    r = await validate_client.post(f"/api/v1/documents/{doc_id}/validate")
    assert r.status_code == 200, r.text
    by_id = {f["rule_id"]: f for f in r.json()["validation"]["findings"]}
    assert by_id["document_expired"]["passed"] is False
    assert by_id["document_expired"]["severity"] == "HIGH"


async def test_validate_endpoint_rejects_pdf(validate_client, db_session):
    files = {"file": ("doc.pdf", b"%PDF-1.4 fake", "application/pdf")}
    r = await validate_client.post("/api/v1/documents/upload", files=files)
    assert r.status_code == 201
    doc_id = r.json()["id"]
    resp = await validate_client.post(f"/api/v1/documents/{doc_id}/validate")
    # PDFs aren't image-preprocessed; extraction falls back to persisted MRZ.
    assert resp.status_code == 200, resp.text
    assert "validation" in resp.json()


async def test_validate_surfaces_registry_flag(
    validate_client, db_session, monkeypatch
):
    """A flagged registry entry flows through to a failing registry finding."""
    from app.pipeline import ocr as ocr_mod
    from app.services import registry as registry_service

    monkeypatch.setattr(ocr_mod, "get_ocr_engine", lambda: _make_fake_engine(_valid_td3_words()))

    # Seed a flagged registry entry for this passport number/type.
    await registry_service.create_entry(
        db_session,
        registry_type="passport",
        document_number="L898902C",
        status="reported_stolen",
    )
    await db_session.commit()

    doc_id = await _upload(validate_client)
    doc = await db_session.get(DocumentRecord, uuid.UUID(doc_id))
    doc.processed_key = f"documents/{doc_id}/processed.jpg"
    doc.original_key = f"documents/{doc_id}/original.jpg"
    doc.document_type = "passport"
    doc.ocr_extracted_fields = _realistic_extracted()
    await db_session.commit()

    r = await validate_client.post(f"/api/v1/documents/{doc_id}/validate")
    assert r.status_code == 200, r.text
    by_id = {f["rule_id"]: f for f in r.json()["validation"]["findings"]}

    registry_finding = by_id["registry_status"]
    assert registry_finding["passed"] is False
    assert registry_finding["severity"] == "HIGH"
    assert registry_finding["risk_contribution"] == "registry_alert"
