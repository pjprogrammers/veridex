"""VERIDEX API - Registry Routes"""

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user
from app.services import registry as registry_service

logger = structlog.get_logger()
router = APIRouter(prefix="/registry", tags=["registry"])


class RegistryCreate(BaseModel):
    registry_type: str = Field(pattern="^[a-z_]+$")
    document_number: str = Field(min_length=4, max_length=20)
    status: str = "valid"
    holder_name: str | None = None
    issuing_country: str | None = Field(default=None, max_length=2)
    additional_data: dict = {}


@router.get("/lookup/{document_number}", response_model=dict)
async def lookup_document(
    document_number: str,
    registry_type: str | None = None,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Look up a document number in the synthetic registry."""
    entries = await registry_service.lookup(db, document_number, registry_type)

    if not entries:
        return {
            "found": False,
            "document_number": document_number,
            "message": "No records found in registry. Document status is unverified.",
        }

    return {
        "found": True,
        "document_number": document_number,
        "entries": [registry_service.entry_to_dict(e) for e in entries],
    }


@router.get("", response_model=dict)
async def list_registry(
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    status_filter: str | None = None,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List registry entries."""
    entries, total = await registry_service.list_entries(
        db, limit, offset, status_filter
    )
    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "entries": [registry_service.entry_to_dict(e) for e in entries],
    }


@router.post("", response_model=dict, status_code=status.HTTP_201_CREATED)
async def create_registry_entry(
    body: RegistryCreate,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a synthetic registry entry (admin only)."""
    if current_user.get("role") != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins can modify the registry",
        )
    try:
        entry = await registry_service.create_entry(
            db,
            registry_type=body.registry_type,
            document_number=body.document_number,
            status=body.status,
            holder_name=body.holder_name,
            issuing_country=body.issuing_country,
            additional_data=body.additional_data,
        )
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    await db.commit()
    await db.refresh(entry)
    return registry_service.entry_to_dict(entry)
