"""VERIDEX API - Verification Pipeline Routes"""
import uuid
from typing import Optional

import structlog
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.database import get_db
from app.core.security import get_current_user
from app.core.storage import download_file
from app.face.engine import get_face_engine
from app.forensics.analyze import run_forensics
from app.models.models import DocumentRecord, StoredFace
from app.pipeline.pipeline import load_image
from app.services.verify import verify_document

logger = structlog.get_logger()
router = APIRouter(prefix="/verification", tags=["verification"])
settings = get_settings()


async def _get_document(db: AsyncSession, document_id: uuid.UUID) -> DocumentRecord:
    doc = await db.get(DocumentRecord, document_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    return doc


async def _load_identity_db(db: AsyncSession) -> list[dict]:
    """Load synthetic identity embeddings from the stored faces table."""
    result = await db.execute(select(StoredFace))
    faces = result.scalars().all()
    return [
        {"identity_id": f.identity_id, "embedding": f.embedding}
        for f in faces
        if f.embedding
    ]


@router.post("/{document_id}/forensics", response_model=dict)
async def analyze_forensics(
    document_id: uuid.UUID,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Run forensic tampering analysis on a stored document."""
    doc = await _get_document(db, document_id)
    data = download_file(settings.MINIO_BUCKET, str(doc.storage_key))
    image = load_image(data)
    result = run_forensics(image)

    doc.forensic_data = {  # type: ignore[assignment]
        "forensic_status": result["forensic_status"],
        "tampering_score": result["tampering_score"],
        "overall_score": result["overall_score"],
        "summary": result["summary"],
        "flags": result["flags"],
        "evidence_note": result.get("evidence_note"),
    }
    await db.commit()

    return {"document_id": document_id, "forensics": result}


@router.post("/{document_id}/face", response_model=dict)
async def analyze_face(
    document_id: uuid.UUID,
    live_face: Optional[UploadFile] = File(None),
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Run face verification: extract portrait, verify against live face,
    and check for duplicate identities in the synthetic database."""
    doc = await _get_document(db, document_id)
    data = download_file(settings.MINIO_BUCKET, str(doc.storage_key))
    document_image = load_image(data)

    live_image = None
    if live_face:
        if live_face.content_type not in ("image/jpeg", "image/png"):
            raise HTTPException(
                status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                detail="Live face must be a JPEG or PNG image",
            )
        live_bytes = await live_face.read()
        if len(live_bytes) > settings.max_upload_size_bytes:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail="Live face image too large",
            )
        live_image = load_image(live_bytes)

    identity_db = await _load_identity_db(db)
    from app.face.analysis import run_face_analysis

    face_result = run_face_analysis(
        document_image=document_image,
        live_face_image=live_image,
        identity_db_embeddings=identity_db or None,
        face_engine=get_face_engine(),
    )
    return {"document_id": document_id, "face": face_result}


@router.get("/{document_id}/report", response_model=dict)
async def get_verification_report(
    document_id: uuid.UUID,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Return the stored verification report for a document without re-running
    the pipeline.

    Returns ``{"verified": false}`` when no report has been produced yet, so a
    client can prompt the officer to run verification instead of recomputing.
    """
    doc = await _get_document(db, document_id)
    stored = doc.verification_data if isinstance(doc.verification_data, dict) else None
    if not stored:
        return {"document_id": str(doc.id), "verified": False}
    return {
        "document_id": str(doc.id),
        "verified": True,
        "verification": stored,
    }


@router.post("/{document_id}/full", response_model=dict)
async def full_verification(
    document_id: uuid.UUID,
    live_face: Optional[UploadFile] = File(None),
    check_registry: bool = True,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Run the complete verification workflow for a document."""
    doc = await _get_document(db, document_id)
    live_bytes = None
    if live_face:
        if live_face.content_type not in ("image/jpeg", "image/png"):
            raise HTTPException(
                status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                detail="Live face must be a JPEG or PNG image",
            )
        live_bytes = await live_face.read()

    identity_db = await _load_identity_db(db)
    registry_status = None
    if check_registry and doc.mrz_data:
        mrz = dict(doc.mrz_data or {})
        doc_number = mrz.get("document_number")
        if doc_number:
            from sqlalchemy import select as _select

            from app.models.models import RegistryEntry

            entry = await db.scalar(
                _select(RegistryEntry).where(
                    RegistryEntry.document_number == str(doc_number)
                )
            )
            if entry:
                registry_status = {"status": entry.status}
    result = await verify_document(
        db,
        doc,
        live_face_bytes=live_bytes,
        identity_db_embeddings=identity_db or None,
        check_registry=check_registry,
        registry_status=registry_status,
    )

    # Roll the risk result up onto the case and record an audit entry.
    from app.models.models import VerificationCase
    from app.services.audit import append_audit_entry

    case = await db.get(VerificationCase, doc.case_id)
    if case:
        risk = result["risk"]
        case.risk_level = risk["level"]  # type: ignore[assignment]
        case.risk_score = risk["score"]  # type: ignore[assignment]
        if risk["level"] in ("HIGH", "CRITICAL"):
            case.status = "flagged"  # type: ignore[assignment]
        await append_audit_entry(
            db,
            case_id=case.id,
            action="verification_completed",
            actor_id=uuid.UUID(current_user["user_id"]),
            actor_role=current_user.get("role"),
            payload={
                "document_id": str(doc.id),
                "risk_level": risk["level"],
                "risk_score": risk["score"],
            },
        )
        await db.commit()

    return {"success": True, "verification": result}
