"""OCR extraction endpoint.

Provides a dedicated API for running OCR on a stored document and
extracting structured fields using configurable per-document-type rules.
"""
from __future__ import annotations

import time
import uuid

import cv2
import numpy as np
import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.database import get_db
from app.core.security import get_current_user
from app.core.storage import download_file
from app.models.models import DocumentRecord
from app.pipeline.ocr import OCRExtractionResult, get_ocr_engine
from app.pipeline.ocr_rules import extract_fields
from app.services.audit import append_audit_entry

settings = get_settings()
logger = structlog.get_logger()

router = APIRouter(prefix="/ocr", tags=["ocr"])


class OCRRequest(BaseModel):
    document_id: str


def _load_image(data: bytes) -> np.ndarray:
    """Decode image bytes into a numpy BGR image."""
    arr = np.frombuffer(data, dtype=np.uint8)
    image = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if image is None:
        raise ValueError("Unable to decode image data")
    return image


@router.post("/v1/extract")
async def extract_ocr(
    body: OCRRequest,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Run OCR on a stored document and extract structured fields.

    Accepts a ``document_id`` (secure reference, not a file path).
    Downloads the processed image (or original fallback) from MinIO,
    runs PaddleOCR, applies document-type-specific extraction rules,
    persists results, and returns the structured output.
    """
    doc_id = body.document_id
    try:
        document_uuid = uuid.UUID(doc_id)
    except ValueError:
        raise HTTPException(status_code=422, detail="Invalid document_id format")

    doc = await db.get(DocumentRecord, document_uuid)
    if doc is None:
        raise HTTPException(status_code=404, detail="Document not found")

    # Determine which image to OCR: prefer processed, fall back to original.
    storage_key = doc.processed_key or doc.original_key
    if not storage_key:
        raise HTTPException(
            status_code=422,
            detail="No image available for OCR (upload a document first)",
        )

    # Download and decode image
    try:
        image_data = download_file(settings.MINIO_BUCKET, str(storage_key))
        image = _load_image(image_data)
    except Exception as exc:
        raise HTTPException(
            status_code=422,
            detail=f"Failed to load image for OCR: {exc}",
        )

    # Run OCR engine with timeout/retry
    t0 = time.monotonic()
    try:
        ocr_engine = get_ocr_engine()
        ocr_result = ocr_engine.run(image)
    except Exception as exc:
        raise HTTPException(
            status_code=422,
            detail=f"OCR engine failed: {exc}",
        )
    elapsed_ms = int((time.monotonic() - t0) * 1000)

    # Apply document-type-specific extraction rules
    document_type = str(doc.document_type or "passport")
    extraction = extract_fields(
        words=ocr_result.words,
        document_type=document_type,
        raw_text=ocr_result.full_text,
    )

    # Build the structured result
    result = OCRExtractionResult(
        fields=[
            {
                "field_name": f.field_name,
                "value": f.value,
                "confidence": f.confidence,
                "bbox": f.bbox,
            }
            for f in extraction.fields
        ],
        raw_text=ocr_result.full_text,
        processing_time_ms=elapsed_ms,
        engine=ocr_result.engine,
    )

    # Persist to DB
    doc.ocr_data = {  # type: ignore[assignment]
        "text": ocr_result.full_text,
        "engine": ocr_result.engine,
        "confidence": ocr_result.confidence,
        "words": ocr_result.words,
    }
    doc.ocr_extracted_fields = {  # type: ignore[assignment]
        "fields": result.fields,
        "document_type": document_type,
        "processing_time_ms": elapsed_ms,
    }

    await append_audit_entry(
        db,
        case_id=doc.case_id,
        action="ocr_extracted",
        actor_id=uuid.UUID(current_user["user_id"]),
        actor_role=current_user.get("role"),
        payload={
            "document_id": doc_id,
            "engine": ocr_result.engine,
            "field_count": len(result.fields),
            "processing_time_ms": elapsed_ms,
        },
    )
    await db.commit()
    await db.refresh(doc)

    logger.info(
        "ocr_extracted",
        document_id=doc_id,
        engine=ocr_result.engine,
        field_count=len(result.fields),
        processing_time_ms=elapsed_ms,
    )

    return result.to_dict()
