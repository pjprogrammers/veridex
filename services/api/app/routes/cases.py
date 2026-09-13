"""VERIDEX API - Case Management Routes"""
import hashlib
import uuid

import structlog
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.database import get_db
from app.core.security import get_current_user
from app.core.storage import upload_file
from app.models.models import DocumentRecord, VerificationCase
from app.schemas.schemas import DocumentUploadResponse, VerificationRequest
from app.services.audit import append_audit_entry

logger = structlog.get_logger()
router = APIRouter(prefix="/cases", tags=["cases"])
settings = get_settings()

VALID_STATUSES = {"in_review", "under_examination", "cleared", "flagged", "closed"}


async def _generate_case_number(db: AsyncSession) -> str:
    """Generate a unique case number like VRX-2026-000001."""
    prefix = "VRX"
    year = "2026"
    count = await db.scalar(select(func.count()).select_from(VerificationCase))
    count = count or 0
    return f"{prefix}-{year}-{count + 1:06d}"


def _case_to_dict(case: VerificationCase) -> dict:
    return {
        "id": str(case.id),
        "case_number": case.case_number,
        "status": case.status,
        "risk_level": case.risk_level,
        "risk_score": case.risk_score,
        "description": case.description,
        "created_at": case.created_at.isoformat() if case.created_at else None,
        "updated_at": case.updated_at.isoformat() if case.updated_at else None,
        "document_hash": case.document_hash,
        "case_metadata": case.case_metadata,
    }


@router.post("", response_model=dict, status_code=status.HTTP_201_CREATED)
async def create_case(
    request: VerificationRequest,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a new verification case."""
    from app.static_demo import known_scenario

    scenario = request.scenario if known_scenario(request.scenario) else None
    case = VerificationCase(
        case_number=await _generate_case_number(db),
        created_by=uuid.UUID(current_user["user_id"]),
        description=request.case_description,
        case_metadata={
            "verify_face_against": request.verify_face_against,
            "check_registry": request.check_registry,
            "perform_forensics": request.perform_forensics,
            "scenario": scenario,
        },
    )
    db.add(case)
    await db.commit()
    await db.refresh(case)

    await append_audit_entry(
        db,
        case_id=case.id,
        action="case_created",
        actor_id=uuid.UUID(current_user["user_id"]),
        actor_role=current_user.get("role"),
        payload={"case_number": case.case_number},
    )
    await db.commit()

    logger.info("case_created", case_id=str(case.id), case_number=case.case_number)
    return _case_to_dict(case)


@router.get("", response_model=dict)
async def list_cases(
    limit: int = 50,
    offset: int = 0,
    status_filter: str | None = None,
    risk_level: str | None = None,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List verification cases with optional filters."""
    query = select(VerificationCase).order_by(VerificationCase.created_at.desc())
    if status_filter and status_filter in VALID_STATUSES:
        query = query.where(VerificationCase.status == status_filter)
    if risk_level:
        query = query.where(VerificationCase.risk_level == risk_level)

    total = await db.scalar(select(func.count()).select_from(query.subquery()))
    result = await db.execute(query.limit(limit).offset(offset))
    cases = result.scalars().all()

    return {
        "total": total or 0,
        "limit": limit,
        "offset": offset,
        "cases": [_case_to_dict(c) for c in cases],
    }


@router.get("/{case_id}", response_model=dict)
async def get_case(
    case_id: uuid.UUID,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get a single case with its documents and checks."""
    case = await db.get(VerificationCase, case_id)
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")

    docs = await db.execute(
        select(DocumentRecord).where(DocumentRecord.case_id == case_id)
    )
    documents = docs.scalars().all()

    return {
        **_case_to_dict(case),
        "documents": [
            {
                "id": str(doc.id),
                "document_type": doc.document_type,
                "content_hash": doc.content_hash,
                "mime_type": doc.mime_type,
                "file_size": doc.file_size,
                "quality_score": doc.quality_score,
                "mrz": doc.mrz_data,
                "extracted_fields": doc.extracted_fields,
                "created_at": doc.created_at.isoformat() if doc.created_at else None,
            }
            for doc in documents
        ],
    }


@router.patch("/{case_id}/status", response_model=dict)
async def update_case_status(
    case_id: uuid.UUID,
    body: dict,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update a case's status with an audit trail entry."""
    case = await db.get(VerificationCase, case_id)
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")

    new_status = body.get("status")
    if new_status not in VALID_STATUSES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid status. Must be one of {sorted(VALID_STATUSES)}",
        )

    old_status = case.status
    case.status = new_status
    await db.flush()

    await append_audit_entry(
        db,
        case_id=case.id,
        action="case_status_changed",
        actor_id=uuid.UUID(current_user["user_id"]),
        actor_role=current_user.get("role"),
        payload={"from": old_status, "to": new_status},
    )
    await db.commit()
    await db.refresh(case)

    logger.info(
        "case_status_changed",
        case_id=str(case.id),
        from_status=old_status,
        to_status=new_status,
    )
    return _case_to_dict(case)


@router.delete("/{case_id}", response_model=dict)
async def delete_case(
    case_id: uuid.UUID,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Delete a case (admin only). Keeps an audit entry before removal."""
    case = await db.get(VerificationCase, case_id)
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    if current_user.get("role") != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins can delete cases",
        )

    await append_audit_entry(
        db,
        case_id=case.id,
        action="case_deleted",
        actor_id=uuid.UUID(current_user["user_id"]),
        actor_role=current_user.get("role"),
        payload={"case_number": case.case_number},
    )
    await db.delete(case)
    await db.commit()
    return {"success": True, "message": "Case deleted"}


@router.post("/{case_id}/documents", response_model=DocumentUploadResponse)
async def upload_document(
    case_id: uuid.UUID,
    file: UploadFile = File(...),
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Upload a document for a case with validation."""
    # Verify case exists
    case = await db.get(VerificationCase, case_id)
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")

    # Validate file size
    content = await file.read()
    if len(content) > settings.max_upload_size_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File exceeds maximum size of {settings.MAX_UPLOAD_SIZE_MB}MB",
        )

    # Validate MIME type
    if file.content_type not in settings.allowed_mime_types:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"Unsupported MIME type: {file.content_type}",
        )

    # Compute SHA-256 hash
    content_hash = hashlib.sha256(content).hexdigest()

    # Check for duplicates
    existing = await db.execute(
        select(DocumentRecord).where(DocumentRecord.content_hash == content_hash)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This document has already been uploaded",
        )

    # Store in MinIO
    ext = (file.filename or "bin").rsplit(".", 1)[-1] if "." in (file.filename or "") else "bin"
    storage_key = f"cases/{case_id}/{uuid.uuid4()}.{ext}"
    upload_file(settings.MINIO_BUCKET, storage_key, content, file.content_type)

    doc = DocumentRecord(
        case_id=case_id,
        storage_key=storage_key,
        content_hash=content_hash,
        mime_type=file.content_type,
        file_size=len(content),
    )
    db.add(doc)
    await db.commit()
    await db.refresh(doc)

    await append_audit_entry(
        db,
        case_id=case_id,
        action="document_uploaded",
        actor_id=uuid.UUID(current_user["user_id"]),
        actor_role=current_user.get("role"),
        payload={"document_id": str(doc.id), "content_hash": content_hash},
    )
    await db.commit()

    logger.info("document_uploaded", document_id=str(doc.id), case_id=str(case_id))

    return DocumentUploadResponse(
        document_id=doc.id,  # type: ignore[arg-type]
        case_id=case_id,
        document_type="unknown",
        storage_key=storage_key,
        content_hash=content_hash,
        quality_score=0.0,
        message="Document uploaded. Processing pipeline will analyze it.",
    )


@router.post("/{case_id}/documents/{document_id}/analyze", response_model=dict)
async def analyze_document(
    case_id: uuid.UUID,
    document_id: uuid.UUID,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Run the document analysis pipeline (quality, OCR, MRZ, doc type) on a stored document."""
    doc = await db.get(DocumentRecord, document_id)
    if not doc or doc.case_id != case_id:
        raise HTTPException(status_code=404, detail="Document not found in this case")

    from app.static_demo import (
        known_scenario,
        scenario_for_document,
        static_analysis,
        static_record_payload,
    )

    scenario_key = await scenario_for_document(db, doc)
    scenario = known_scenario(scenario_key)
    if scenario:
        payload = static_record_payload(scenario)
        doc.document_type = payload["document_type"]  # type: ignore[assignment]
        doc.quality_score = payload["quality_score"]  # type: ignore[assignment]
        doc.mrz_data = payload["mrz_data"]  # type: ignore[assignment]
        doc.extracted_fields = payload["extracted_fields"]  # type: ignore[assignment]
        doc.classification_data = payload["classification_data"]  # type: ignore[assignment]
        doc.ocr_extracted_fields = payload["ocr_extracted_fields"]  # type: ignore[assignment]
        doc.forensic_data = payload["forensic_data"]  # type: ignore[assignment]
        await db.commit()

        await append_audit_entry(
            db,
            case_id=case_id,
            action="document_analyzed",
            actor_id=uuid.UUID(current_user["user_id"]),
            actor_role=current_user.get("role"),
            payload={
                "document_id": str(doc.id),
                "document_type": payload["document_type"],
                "demo_scenario": scenario_key,
            },
        )
        await db.commit()
        return {"success": True, "analysis": static_analysis(scenario, str(doc.id)), "demo": True}

    from app.services.document_analysis import run_document_analysis

    result = await run_document_analysis(db, doc)

    await append_audit_entry(
        db,
        case_id=case_id,
        action="document_analyzed",
        actor_id=uuid.UUID(current_user["user_id"]),
        actor_role=current_user.get("role"),
        payload={
            "document_id": str(doc.id),
            "document_type": result["document_type"],
        },
    )
    await db.commit()

    return {"success": True, "analysis": result}
