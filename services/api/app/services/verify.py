"""Verification orchestrator.

Runs the full verification workflow for a case: document pipeline analysis,
forensic tampering checks, face verification, field validation, OCR-vs-MRZ
cross-validation, and the explainable risk engine. Produces a structured,
persistable verification result with cautious, decision-support language.
"""
from typing import Optional

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.storage import download_file
from app.face.analysis import run_face_analysis
from app.face.engine import get_face_engine
from app.forensics.analyze import run_forensics
from app.models.models import DocumentRecord
from app.pipeline.pipeline import analyze_document, load_image
from app.risk.engine import RiskResult, risk_engine
from app.validation.cross_validate import cross_validate_ocr_mrz
from app.validation.fields import validate_fields

settings = get_settings()
logger = structlog.get_logger()

DISCLAIMER = (
    "This is a decision-support analysis. It does not prove authenticity or "
    "fraud. Manual review by an officer is required before any enforcement "
    "action."
)


def _validate_analysis(document_analysis) -> dict:
    """Run field validation + OCR-vs-MRZ cross-validation outputs."""
    extracted = document_analysis.extracted_fields
    validation = validate_fields(extracted) if extracted else {}

    # OCR-vs-MRZ cross-validation
    mrz = document_analysis.mrz or {}
    # For cross-validation we need OCR-read equivalents of the MRZ fields.
    # Build an OCR-only view from the human-readable printed fields detected
    # in the raw OCR word boxes (independent of the MRZ zone).
    ocr_view = _ocr_field_view(document_analysis.ocr_words)
    cross = cross_validate_ocr_mrz(ocr_view, mrz)

    return {
        "field_validation": validation,
        "cross_validation": cross,
    }


def _ocr_field_view(words: list[dict]) -> dict:
    """Best-effort structured field extraction from OCR words.

    Uses a deterministic, label-driven parser over the printed fields on the
    document face (independent of the MRZ zone). In the AI pipeline this is
    fed by PaddleOCR structured output; the baseline engine produces no word
    boxes, in which case an empty view is returned and cross-validation
    reports those fields as missing.
    """
    from app.pipeline.field_parser import extract_fields_from_words

    return extract_fields_from_words(words or [])


async def verify_document(
    db: AsyncSession,
    document: DocumentRecord,
    live_face_bytes: Optional[bytes] = None,
    identity_db_embeddings: Optional[list[dict]] = None,
    check_registry: bool = True,
    registry_status: Optional[dict] = None,
) -> dict:
    """Run the complete verification for a single document."""
    data = download_file(settings.MINIO_BUCKET, str(document.storage_key))
    image = load_image(data)

    # 1. Document pipeline (quality, OCR, MRZ, type)
    document_analysis = analyze_document(image)

    # 2. Forensics
    forensics = run_forensics(image)

    # 3. Face verification (portrait + optional live face + duplicates)
    live_face = load_image(live_face_bytes) if live_face_bytes else None
    face_analysis = run_face_analysis(
        document_image=image,
        live_face_image=live_face,
        identity_db_embeddings=identity_db_embeddings,
        face_engine=get_face_engine(),
    )

    # 4. Validation & cross-validation
    validation = _validate_analysis(document_analysis)

    # 5. Explainable risk engine
    risk: RiskResult = risk_engine.compute(
        document_analysis={
            "quality": document_analysis.quality,
            "mrz": document_analysis.mrz,
        },
        forensics=forensics,
        face=face_analysis,
        registry=registry_status,
        validation=validation["field_validation"],
        cross_validation=validation["cross_validation"],
    )

    result = {
        "document_id": str(document.id),
        "document_type": document_analysis.document_type,
        "quality": document_analysis.quality,
        "mrz": document_analysis.mrz,
        "ocr_confidence": document_analysis.ocr_confidence,
        "forensics": forensics,
        "face": {
            "verification": face_analysis.get("verification"),
            "liveness": face_analysis.get("liveness"),
            "duplicate_identity": face_analysis.get("duplicate_identity"),
            "portrait_bbox": face_analysis.get("portrait", {}).get("bbox"),
        },
        "field_validation": validation["field_validation"],
        "cross_validation": validation["cross_validation"],
        "risk": {
            "score": risk.score,
            "level": risk.level,
            "factors": risk.factors,
            "explanation": risk.explanation,
        },
        "recommendation": risk.explanation,
        "disclaimer": DISCLAIMER,
    }

    # Persist forensic + face data onto the record
    document.forensic_data = _safe_forensic_payload(forensics)  # type: ignore[assignment]
    document.extracted_fields = document_analysis.extracted_fields  # type: ignore[assignment]
    await db.commit()

    logger.info(
        "document_verified",
        document_id=str(document.id),
        risk_level=risk.level,
        risk_score=risk.score,
    )
    return result


def _safe_forensic_payload(forensics: dict) -> dict:
    """Strip high-cardinality/full arrays to keep the stored payload lean."""
    return {
        "overall_score": forensics.get("overall_score"),
        "summary": forensics.get("summary"),
        "flags": forensics.get("flags"),
    }
