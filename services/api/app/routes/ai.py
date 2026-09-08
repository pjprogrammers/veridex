"""VERIDEX API — AI/CV showcase routes.

Thin HTTP surface over the standalone ``ai`` package at the repository root.
Endpoints are lazy-loaded so the API stays healthy when the heavy AI
dependencies are not installed (they answer 503 with a clear reason). Every
payload returned is the structured, evidence-only output of the AI layer — no
business-risk decisions are made here.
"""
from __future__ import annotations

import uuid

import cv2
import numpy as np
import structlog
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.ai_bridge import ai_available, ai_stack
from app.core.config import get_settings
from app.core.database import get_db
from app.core.security import get_current_user
from app.core.storage import download_file
from app.models.models import DocumentRecord

logger = structlog.get_logger()
router = APIRouter(prefix="/ai", tags=["ai-showcase"])
settings = get_settings()

MODEL_UNAVAILABLE_TEXT = (
    "The AI/CV layer or its heavy dependencies (PaddleOCR / InsightFace) are not "
    "installed in this environment. Install services/api/requirements-ai.txt to "
    "enable the showcase."
)


class OCREnvelope(BaseModel):
    document_id: str
    document_type: str = "generic"


def _decode_image(data: bytes, label: str) -> np.ndarray:
    arr = np.frombuffer(data, dtype=np.uint8)
    image = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if image is None:
        raise HTTPException(
            status_code=422,
            detail=f"{label} could not be decoded as an image",
        )
    return image


def _load_ai():
    """Return (run_ocr, run_face_verification) or raise a clean 503."""
    if not ai_available():
        raise HTTPException(status_code=503, detail=MODEL_UNAVAILABLE_TEXT)
    from ai import run_face_verification, run_ocr

    return run_ocr, run_face_verification


@router.get("/status")
async def status(
    current_user: dict = Depends(get_current_user),
) -> dict:
    """Describe the reusable AI/CV layer and locally provisioned models."""
    return ai_stack()


@router.post("/ocr/upload")
async def ocr_upload(
    file: UploadFile = File(...),
    document_type: str = Form("generic"),
    current_user: dict = Depends(get_current_user),
) -> dict:
    """Run the full OCR pipeline on a directly uploaded document image.

    Accepts JPEG/PNG/WEBP/PDF, runs preprocess -> PaddleOCR -> fields -> MRZ,
    and returns the complete structured result (raw JSON contract of the AI layer).
    """
    run_ocr, _ = _load_ai()
    content = await file.read()
    if not content:
        raise HTTPException(status_code=422, detail="Uploaded file is empty")
    image = _decode_image(content, file.filename or "file")
    result = run_ocr(image, document_type=document_type)
    payload = result.model_dump(mode="json")
    _log_ocr(current_user, document_type=document_type, payload=payload)
    return payload


@router.post("/ocr")
async def ocr_document(
    body: OCREnvelope,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Run OCR on an already-uploaded document (fetched from MinIO)."""
    run_ocr, _ = _load_ai()
    try:
        document_uuid = uuid.UUID(body.document_id)
    except ValueError:
        raise HTTPException(status_code=422, detail="Invalid document_id format")

    doc = await db.get(DocumentRecord, document_uuid)
    if doc is None:
        raise HTTPException(status_code=404, detail="Document not found")

    storage_key = doc.processed_key or doc.original_key or doc.storage_key
    if not storage_key:
        raise HTTPException(
            status_code=422,
            detail="No image available for OCR on this document",
        )

    try:
        data = download_file(settings.MINIO_BUCKET, str(storage_key))
        image = _decode_image(data, "document")
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            status_code=422, detail=f"Failed to load document image: {exc}"
        )

    result = run_ocr(image, document_type=body.document_type)
    payload = result.model_dump(mode="json")
    _log_ocr(current_user, document_type=body.document_type, payload=payload)
    return payload


@router.post("/face/verify")
async def face_verify(
    document_image: UploadFile = File(...),
    live_image: UploadFile = File(...),
    threshold: float | None = Form(None),
    current_user: dict = Depends(get_current_user),
) -> dict:
    """Verify a document portrait against a live/user face photo.

    Runs detection, quality, embedding and cosine-similarity on both faces and
    returns the AI layer's MATCH / NO_MATCH / INCONCLUSIVE verdict plus signal
    detail — evidence only, never a business decision.
    """
    _, run_face_verification = _load_ai()
    doc_data = await document_image.read()
    live_data = await live_image.read()
    if not doc_data or not live_data:
        raise HTTPException(status_code=422, detail="Both images are required")
    doc_image = _decode_image(doc_data, "document_image")
    live = _decode_image(live_data, "live_image")
    result = run_face_verification(doc_image, live, threshold=threshold)
    payload = result.model_dump(mode="json")
    logger.info(
        "ai_face_verify",
        actor_id=current_user.get("user_id"),
        result=payload.get("result"),
        similarity=payload.get("similarity"),
    )
    return payload


def _log_ocr(current_user: dict, *, document_type: str, payload: dict) -> None:
    logger.info(
        "ai_ocr_ran",
        actor_id=current_user.get("user_id"),
        document_type=document_type,
        engine=payload.get("engine"),
        field_count=len(payload.get("fields") or {}),
        mrz_detected=bool(payload.get("mrz") and payload["mrz"].get("detected")),
        total_latency_ms=payload.get("latency_ms", {}).get("total_latency_ms"),
        error=payload.get("error"),
    )
