"""VERIDEX API - Document Ingestion Routes

Phase 3 ingestion + preprocessing. Documents move through states
UPLOADED -> VALIDATING -> PREPROCESSING -> READY (or FAILED). The
original is stored unmodified; preprocessing produces separate
processed and preview objects.
"""
import hashlib
import uuid
from datetime import date

import numpy as np
import structlog
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.document_states import (
    DOCUMENT_STATE_CLASSIFYING,
    DOCUMENT_STATE_FAILED,
    DOCUMENT_STATE_PREPROCESSING,
    DOCUMENT_STATE_READY,
    DOCUMENT_STATE_UPLOADED,
    DOCUMENT_STATE_VALIDATING,
)
from app.models.models import DocumentRecord
from app.pipeline.preprocess import run_ingestion_preprocess
from app.services.audit import append_audit_entry
from app.services.ingestion import (
    DocumentUploadError,
    load_original,
    sanitize_filename,
    store_original,
    store_processed,
    validate_upload,
    verify_image_integrity,
)

logger = structlog.get_logger()
router = APIRouter(prefix="/documents", tags=["documents"])


async def _get_document(db: AsyncSession, document_id: uuid.UUID) -> DocumentRecord:
    doc = await db.get(DocumentRecord, document_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    return doc


def _document_to_dict(doc: DocumentRecord) -> dict:
    return {
        "id": str(doc.id),
        "case_id": str(doc.case_id) if doc.case_id else None,
        "document_type": doc.document_type,
        "status": doc.status,
        "original_filename": doc.original_filename,
        "mime_type": doc.mime_type,
        "file_size": doc.file_size,
        "content_hash": doc.content_hash,
        "quality_score": doc.quality_score,
        "preprocess": doc.preprocess_metadata or {},  # type: ignore[union-attr]
        "original_key": doc.original_key,
        "processed_key": doc.processed_key,
        "preview_key": doc.preview_key,
        "processing_error": doc.processing_error,
        "classification": doc.classification_data or {},  # type: ignore[union-attr]
        "ocr_extracted_fields": doc.ocr_extracted_fields or {},  # type: ignore[union-attr]
        "created_at": doc.created_at.isoformat() if doc.created_at else None,
        "updated_at": doc.updated_at.isoformat() if doc.updated_at else None,
    }


@router.post("/upload", response_model=dict, status_code=201)
async def upload_document(
    file: UploadFile = File(...),
    case_id: uuid.UUID | None = None,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Ingest an uploaded document.

    Validates MIME + extension + size, rejects corrupt/unparseable images,
    stores the object in MinIO, and records metadata in PostgreSQL. The
    document is placed in UPLOADED state.
    """
    content = await file.read()
    safe_name = sanitize_filename(file.filename)

    try:
        mime = validate_upload(file.filename, file.content_type, len(content))
        if mime == "application/pdf":
            # PDFs are accepted for storage but not image-preprocessed here.
            image, canonical_mime = None, mime
            image_postproc = False
        else:
            image, canonical_mime = verify_image_integrity(content)
            image_postproc = True
    except DocumentUploadError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message)

    content_hash = hashlib.sha256(content).hexdigest()
    existing = await db.execute(
        select(DocumentRecord).where(DocumentRecord.content_hash == content_hash)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=409,
            detail="This document has already been uploaded",
        )

    doc = DocumentRecord(
        case_id=case_id,
        status=DOCUMENT_STATE_UPLOADED,
        original_filename=safe_name,
        mime_type=mime,
        file_size=len(content),
        content_hash=content_hash,
    )
    db.add(doc)
    await db.flush()

    ext = "pdf" if mime == "application/pdf" else "jpg"
    storage_key = store_original(content, mime, str(doc.id), str(case_id) if case_id else None, ext)
    doc.storage_key = storage_key  # type: ignore[assignment]
    doc.original_key = storage_key  # type: ignore[assignment]
    # Hold posture: image documents are ready to validate/preprocess.
    doc.status = DOCUMENT_STATE_VALIDATING if image_postproc else DOCUMENT_STATE_UPLOADED  # type: ignore[assignment]

    await db.commit()
    await db.refresh(doc)

    await append_audit_entry(
        db,
        case_id=doc.case_id,
        action="document_uploaded",
        actor_id=uuid.UUID(current_user["user_id"]),
        actor_role=current_user.get("role"),
        payload={
            "document_id": str(doc.id),
            "content_hash": content_hash,
            "mime_type": mime,
            "file_size": len(content),
            "image_preprocessable": image_postproc,
        },
    )
    await db.commit()

    logger.info(
        "document_uploaded",
        document_id=str(doc.id),
        case_id=str(doc.case_id) if doc.case_id else None,
        mime_type=mime,
    )
    return _document_to_dict(doc)


@router.post("/{document_id}/preprocess", response_model=dict)
async def preprocess_document(
    document_id: uuid.UUID,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Preprocess a stored document image.

    Runs orientation correction, boundary detection, perspective crop,
    resolution normalization, denoising, contrast enhancement, and
    adaptive sharpening. Stores the processed and preview images as
    separate MinIO objects and records preprocessing metadata. Producing
    an OCR-ready image does not guarantee OCR accuracy.
    """
    doc = await _get_document(db, document_id)

    if doc.mime_type == "application/pdf":
        raise HTTPException(
            status_code=422,
            detail="Preprocessing is only supported for image documents (JPEG/PNG/WEBP)",
        )

    doc.status = DOCUMENT_STATE_PREPROCESSING  # type: ignore[assignment]
    doc.processing_error = None  # type: ignore[assignment]
    await db.commit()

    try:
        data = load_original(doc.storage_key)  # type: ignore[arg-type]
        image, _ = verify_image_integrity(data)

        result = run_ingestion_preprocess(image)
        processed_key = store_processed(
            result["processed"], str(doc.id), str(doc.case_id) if doc.case_id else None, "processed"
        )
        preview_key = store_processed(
            result["preview"], str(doc.id), str(doc.case_id) if doc.case_id else None, "preview"
        )

        metadata = result["metadata"]
        doc.processed_key = processed_key  # type: ignore[assignment]
        doc.preview_key = preview_key  # type: ignore[assignment]
        doc.preprocess_metadata = metadata  # type: ignore[assignment]
        doc.quality_score = metadata["quality_score"]  # type: ignore[assignment]
        doc.status = DOCUMENT_STATE_READY  # type: ignore[assignment]
    except Exception as exc:  # noqa: BLE001
        doc.status = DOCUMENT_STATE_FAILED  # type: ignore[assignment]
        doc.processing_error = str(exc)  # type: ignore[assignment]
        await db.commit()
        logger.error(
            "document_preprocess_failed", document_id=str(doc.id), error=str(exc)
        )
        raise HTTPException(
            status_code=422,
            detail=f"Preprocessing failed: {exc}",
        )

    await db.commit()
    await db.refresh(doc)

    await append_audit_entry(
        db,
        case_id=doc.case_id,
        action="document_preprocessed",
        actor_id=uuid.UUID(current_user["user_id"]),
        actor_role=current_user.get("role"),
        payload={
            "document_id": str(doc.id),
            "status": DOCUMENT_STATE_READY,
            "quality_score": metadata["quality_score"],
            "width": metadata["width"],
            "height": metadata["height"],
        },
    )
    await db.commit()

    logger.info(
        "document_preprocessed",
        document_id=str(doc.id),
        quality=metadata["quality_score"],
    )
    return _document_to_dict(doc)


@router.get("/{document_id}", response_model=dict)
async def get_document(
    document_id: uuid.UUID,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get a document's metadata, ingestion state, and preprocessing results."""
    doc = await _get_document(db, document_id)
    return _document_to_dict(doc)


@router.post("/{document_id}/classify", response_model=dict)
async def classify_document(
    document_id: uuid.UUID,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Classify the document type using the heuristic classifier.

    Downloads the original image from MinIO, runs the classifier, and
    persists the result.  Updates ``document_type`` and stores the full
    classification output in ``classification_data``.
    """
    doc = await _get_document(db, document_id)

    if doc.mime_type == "application/pdf":
        raise HTTPException(
            status_code=422,
            detail="Classification is only supported for image documents (JPEG/PNG/WEBP)",
        )

    doc.status = DOCUMENT_STATE_CLASSIFYING  # type: ignore[assignment]
    doc.processing_error = None  # type: ignore[assignment]
    await db.commit()

    try:
        data = load_original(doc.original_key or doc.storage_key)  # type: ignore[arg-type]
        image, _ = verify_image_integrity(data)

        from app.pipeline.heuristic_classifier import HeuristicClassifier

        classifier = HeuristicClassifier()
        result = classifier.classify(
            image,
            ocr_text="",
            preprocess_metadata=dict(doc.preprocess_metadata) if doc.preprocess_metadata else {},  # type: ignore[arg-type]
        )
        result_dict = result.to_dict()

        doc.classification_data = result_dict  # type: ignore[assignment]
        doc.document_type = result.document_type  # type: ignore[assignment]
        doc.status = DOCUMENT_STATE_READY  # type: ignore[assignment]
    except Exception as exc:  # noqa: BLE001
        doc.status = DOCUMENT_STATE_FAILED  # type: ignore[assignment]
        doc.processing_error = str(exc)  # type: ignore[assignment]
        await db.commit()
        logger.error(
            "document_classify_failed", document_id=str(doc.id), error=str(exc)
        )
        raise HTTPException(
            status_code=422,
            detail=f"Classification failed: {exc}",
        )

    await db.commit()
    await db.refresh(doc)

    await append_audit_entry(
        db,
        case_id=doc.case_id,
        action="document_classified",
        actor_id=uuid.UUID(current_user["user_id"]),
        actor_role=current_user.get("role"),
        payload={
            "document_id": str(doc.id),
            "document_type": result.document_type,
            "confidence": result.confidence,
            "method": result.method,
            "warnings": result.warnings,
        },
    )
    await db.commit()

    logger.info(
        "document_classified",
        document_id=str(doc.id),
        document_type=result.document_type,
        confidence=result.confidence,
    )
    return _document_to_dict(doc)


@router.post("/{document_id}/mrz", response_model=dict)
async def extract_mrz(
    document_id: uuid.UUID,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Run MRZ region detection + ICAO parsing + visual-vs-MRZ comparison.

    Downloads the processed image, runs OCR, detects the dense MRZ region,
    parses and validates the machine-readable zone (including ICAO check
    digits), and compares it against the rule-extracted visual fields when
    they are available.
    """
    from app.pipeline.mrz import parse_mrz
    from app.pipeline.mrz_region import extract_mrz_from_words
    from app.validation.mrz_compare import compare_visual_mrz

    doc = await _get_document(db, document_id)

    if doc.mime_type == "application/pdf":
        raise HTTPException(
            status_code=422,
            detail="MRZ extraction is only supported for image documents (JPEG/PNG/WEBP)",
        )

    try:
        from app.pipeline.ocr import get_ocr_engine

        ocr_engine = get_ocr_engine()
        data = load_original(doc.processed_key or doc.storage_key or doc.original_key)  # type: ignore[arg-type]
        image, _ = verify_image_integrity(data)
        ocr_result = ocr_engine.run(image)
        words = ocr_result.words or []

        region = extract_mrz_from_words(words)
        mrz_result = parse_mrz(region.lines) if region.detected else None

        mrz_payload: dict = {
            "mrz_detected": bool(mrz_result and mrz_result.mrz_detected),
            "mrz_valid": bool(mrz_result and mrz_result.mrz_valid),
            "check_digits": (mrz_result.check_digits if mrz_result else {}),
            "parsed_fields": (mrz_result.parsed_fields if mrz_result else {}),
            "raw_mrz": (mrz_result.raw_mrz if mrz_result else region.lines),
            "warnings": (mrz_result.warnings if mrz_result else region.warnings),
        }

        # Visual-vs-MRZ comparison when we have both views and a classifiable doc.
        comparison = None
        visual_fields: dict[str, str] = {}
        if doc.classification_data and mrz_result and mrz_result.mrz_detected:
            ocr_fields = dict(doc.ocr_extracted_fields or {})
            visual_fields = {
                "passport_number": (ocr_fields.get("passport_number") or {}).get("value", ""),
                "full_name": (ocr_fields.get("full_name") or {}).get("value", ""),
                "date_of_birth": (ocr_fields.get("date_of_birth") or {}).get("value", ""),
                "nationality": (ocr_fields.get("nationality") or {}).get("value", ""),
                "date_of_expiry": (ocr_fields.get("date_of_expiry") or {}).get("value", ""),
            }
            mrz_fields = {
                "passport_number": mrz_result.parsed_fields.get("passport_number", ""),
                "name": mrz_result.parsed_fields.get("given_names", "")
                + " " + mrz_result.parsed_fields.get("surname", ""),
                "date_of_birth": mrz_result.parsed_fields.get("date_of_birth", ""),
                "nationality": mrz_result.parsed_fields.get("nationality", ""),
                "expiry_date": mrz_result.parsed_fields.get("expiry_date", ""),
            }
            comparison = compare_visual_mrz(visual_fields, mrz_fields).to_dict()

    except Exception as exc:  # noqa: BLE001
        logger.error("document_mrz_failed", document_id=str(doc.id), error=str(exc))
        raise HTTPException(
            status_code=422,
            detail=f"MRZ extraction failed: {exc}",
        ) from exc

    return {
        "document_id": str(doc.id),
        "document_type": doc.document_type,
        "mrz": mrz_payload,
        "visual_fields": visual_fields,
        "comparison": comparison,
    }


@router.post("/{document_id}/validate", response_model=dict)
async def validate_document(
    document_id: uuid.UUID,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Run the rule-based validation engine over a document.

    Combines the extracted (visual) fields, MRZ data, document type, current
    date and registry lookups into a set of validation *findings*. Findings
    describe whether each rule passed and how severe a failure is; they do not
    produce a numeric risk score.
    """
    from app.validation.engine import validate

    doc = await _get_document(db, document_id)

    # Visual (rule-extracted) fields.
    ocr_fields = dict(doc.ocr_extracted_fields or {})
    extracted_data = {
        "passport_number": (ocr_fields.get("passport_number") or {}).get("value", ""),
        "document_number": (ocr_fields.get("document_number") or {}).get("value", ""),
        "full_name": (ocr_fields.get("full_name") or {}).get("value", ""),
        "date_of_birth": (ocr_fields.get("date_of_birth") or {}).get("value", ""),
        "date_of_issue": (ocr_fields.get("date_of_issue") or {}).get("value", ""),
        "date_of_expiry": (ocr_fields.get("date_of_expiry") or {}).get("value", ""),
        "nationality": (ocr_fields.get("nationality") or {}).get("value", ""),
        "sex": (ocr_fields.get("sex") or {}).get("value", ""),
    }

    # MRZ data: prefer re-running the extraction for full structured fields,
    # falling back to whatever was persisted by the pipeline.
    mrz_payload = {}
    try:
        from app.pipeline.mrz import parse_mrz
        from app.pipeline.mrz_region import extract_mrz_from_words
        from app.pipeline.ocr import get_ocr_engine

        ocr_engine = get_ocr_engine()
        data = load_original(doc.processed_key or doc.storage_key or doc.original_key)  # type: ignore[arg-type]
        image, _ = verify_image_integrity(data)
        ocr_result = ocr_engine.run(image)
        words = ocr_result.words or []
        region = extract_mrz_from_words(words)
        mrz_result = parse_mrz(region.lines) if region.detected else None
        mrz_payload = {
            "mrz_detected": bool(mrz_result and mrz_result.mrz_detected),
            "mrz_valid": bool(mrz_result and mrz_result.mrz_valid),
            "check_digits": (mrz_result.check_digits if mrz_result else {}),
            "parsed_fields": (mrz_result.parsed_fields if mrz_result else {}),
            "raw_mrz": (mrz_result.raw_mrz if mrz_result else region.lines),
            "warnings": (mrz_result.warnings if mrz_result else region.warnings),
        }
    except Exception:  # noqa: BLE001
        # Fall back to persisted MRZ data (flattened fields reconstructed).
        persisted = dict(doc.mrz_data or {})
        if persisted and persisted.get("mrz_detected"):
            mrz_payload = {
                "mrz_detected": True,
                "mrz_valid": bool(persisted.get("mrz_valid")),
                "check_digits": persisted.get("check_digits") or {},
                "parsed_fields": {
                    "passport_number": persisted.get("document_number", ""),
                    "surname": persisted.get("surname", ""),
                    "given_names": persisted.get("given_names", ""),
                    "date_of_birth": persisted.get("date_of_birth", ""),
                    "sex": persisted.get("sex", ""),
                    "expiry_date": persisted.get("expiry_date", ""),
                    "nationality": persisted.get("nationality", ""),
                    "issuing_state": persisted.get("issuing_country", ""),
                },
                "raw_mrz": persisted.get("raw_lines", []),
                "warnings": persisted.get("warnings", []),
            }

    # Document type / country.
    classification = dict(doc.classification_data or {})
    document_type = str(doc.document_type or classification.get("document_type") or "")
    document_country = str(doc.country or classification.get("country") or "")

    # Registry lookups by the extracted passport/document number.
    registry_entries: list[dict] = []
    from app.services import registry as registry_service

    for doc_number in (extracted_data["passport_number"], extracted_data["document_number"]):
        if doc_number:
            try:
                entries = await registry_service.lookup(db, doc_number, str(document_type or "").lower())
                registry_entries.extend(registry_service.entry_to_dict(e) for e in entries)
            except Exception:  # noqa: BLE001
                pass

    # Cross-document consistency: other documents in the same case.
    other_documents: list[dict] = []
    if doc.case_id:
        from sqlalchemy import select

        siblings = (
            await db.execute(
                select(DocumentRecord).where(
                    DocumentRecord.case_id == doc.case_id, DocumentRecord.id != doc.id
                )
            )
        ).scalars().all()
        for sibling in siblings:
            sibling_fields = dict(sibling.ocr_extracted_fields or {})
            other_documents.append(
                {
                    "id": str(sibling.id),
                    "fields": {
                        "full_name": (sibling_fields.get("full_name") or {}).get("value", ""),
                        "date_of_birth": (sibling_fields.get("date_of_birth") or {}).get("value", ""),
                        "nationality": (sibling_fields.get("nationality") or {}).get("value", ""),
                    },
                }
            )

    result = validate(
        extracted_data=extracted_data,
        mrz=mrz_payload,
        document_type=document_type,
        document_country=document_country,
        registry=registry_entries,
        other_documents=other_documents,
    )

    return {
        "document_id": str(doc.id),
        "document_type": document_type,
        "current_date": date.today().isoformat(),
        "validation": result.to_dict(),
    }


@router.post("/{document_id}/forensics", response_model=dict)
async def run_forensics(
    document_id: uuid.UUID,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Run the modular forensic engine over a document image.

    Loads the stored original, runs the pluggable detector set, fuses their
    findings into a "potential manipulation indicator", persists the structured
    result on the document, and returns the analysis with inline artifact views.
    All outputs are framed as supporting signals, never a forgery verdict.
    """
    from app.forensics.engine import forensic_pipeline

    doc = await _get_document(db, document_id)

    data = load_original(doc.processed_key or doc.storage_key or doc.original_key)  # type: ignore[arg-type]
    image, _ = verify_image_integrity(data)
    ctx: dict = {"raw_bytes": data}

    result = forensic_pipeline.run(image, ctx)
    payload = result.to_dict()

    # Persist structured findings (drop inline byte artifacts to avoid huge
    # JSON blobs, but keep their presence marker + store PNG artifacts to MinIO).
    artifact_keys: dict[str, str] = {}
    case_prefix = str(doc.case_id) if doc.case_id else None
    for finding in result.findings:
        for name, raw in (finding.artifacts or {}).items():
            if not raw:
                continue
            kind = f"forensics_{finding.detector_id}_{name}"
            key = store_processed(_decode_png(bytes(raw)), str(doc.id), case_prefix, kind)
            artifact_keys[f"{finding.detector_id}:{name}"] = key

    doc.forensic_data = {  # type: ignore[assignment]
        "forensic_status": payload["forensic_status"],
        "tampering_score": payload["tampering_score"],
        "level": payload["level"],
        "explanation": payload["explanation"],
        "weights": payload["weights"],
        "components": payload["components"],
        "regions": payload["regions"],
        "detectors": [
            {
                "detector_id": d["detector_id"],
                "detector_name": d["detector_name"],
                "score": d["score"],
                "severity": d["severity"],
                "description": d["description"],
                "evidence": d["evidence"],
                "detector_status": d.get("detector_status", "experimental"),
            }
            for d in payload["detectors"]
        ],
        "artifact_keys": artifact_keys,
    }
    payload["artifact_keys"] = artifact_keys

    await db.commit()

    return {
        "document_id": str(doc.id),
        "forensic_status": payload["forensic_status"],
        "tampering_score": payload["tampering_score"],
        "level": payload["level"],
        "explanation": payload["explanation"],
        "weights": payload["weights"],
        "components": payload["components"],
        "regions": payload["regions"],
        "detectors": payload["detectors"],
        "artifact_keys": artifact_keys,
    }


@router.get("/{document_id}/forensics", response_model=dict)
async def get_forensics(
    document_id: uuid.UUID,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Return the persisted forensic analysis for a document (if any)."""
    doc = await _get_document(db, document_id)
    data = dict(doc.forensic_data or {})
    if not data:
        raise HTTPException(status_code=404, detail="No forensics available for this document")
    return {"document_id": str(doc.id), "forensics": data}


def _decode_png(raw: bytes) -> np.ndarray:
    """Decode a stored PNG byte string back to a BGR numpy array."""
    import cv2

    buf = np.frombuffer(raw, dtype=np.uint8)
    img = cv2.imdecode(buf, cv2.IMREAD_COLOR)
    if img is None:
        img = np.zeros((10, 10, 3), dtype=np.uint8)
    return img
