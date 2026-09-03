"""VERIDEX API - Audit Trail Routes"""
import uuid

import structlog
from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.models import AuditLog
from app.schemas.schemas import AuditEntryResponse
from app.services.audit import verify_chain

logger = structlog.get_logger()
router = APIRouter(prefix="/audit", tags=["audit"])


@router.get("", response_model=list[AuditEntryResponse])
async def list_audit_logs(
    case_id: uuid.UUID | None = None,
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List audit log entries, optionally filtered by case."""
    query = select(AuditLog).order_by(AuditLog.timestamp.desc())
    if case_id:
        query = query.where(AuditLog.case_id == case_id)
    query = query.limit(limit).offset(offset)

    result = await db.execute(query)
    return result.scalars().all()


@router.get("/verify/{case_id}")
async def verify_audit_chain(
    case_id: uuid.UUID,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Verify the integrity of the tamper-evident audit trail for a case."""
    result = await verify_chain(db, case_id)
    result["message"] = (
        "Audit trail integrity confirmed."
        if result["valid"]
        else "Audit trail integrity VIOLATED. Immediate investigation required."
    )
    return result
