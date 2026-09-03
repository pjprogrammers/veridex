"""Synthetic registry service.

Provides lookups and CRUD for the local/synthetic document registry. The
registry approximates a government document-status source of truth for the
prototype. Statuses use cautious language and never assert criminality.
"""
from typing import Optional

import structlog
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.models import RegistryEntry

logger = structlog.get_logger()

VALID_STATUSES = {"valid", "reported_stolen", "blacklisted", "watchlist", "expired"}
VALID_TYPES = {"passport", "national_id", "drivers_license", "residence_permit", "immigration"}


async def create_entry(
    db: AsyncSession,
    *,
    registry_type: str,
    document_number: str,
    status: str = "valid",
    holder_name: Optional[str] = None,
    issuing_country: Optional[str] = None,
    additional_data: Optional[dict] = None,
) -> RegistryEntry:
    """Create a registry entry."""
    if registry_type not in VALID_TYPES:
        raise ValueError(f"Invalid registry type: {registry_type}")
    if status not in VALID_STATUSES:
        raise ValueError(f"Invalid status: {status}")

    entry = RegistryEntry(
        registry_type=registry_type,
        document_number=document_number,
        status=status,
        holder_name=holder_name,
        issuing_country=issuing_country,
        additional_data=additional_data or {},
    )
    db.add(entry)
    await db.flush()
    logger.info("registry_entry_created", document_number=document_number)
    return entry


async def lookup(
    db: AsyncSession,
    document_number: str,
    registry_type: Optional[str] = None,
) -> list[RegistryEntry]:
    """Look up entries by document number."""
    query = select(RegistryEntry).where(
        RegistryEntry.document_number == document_number
    )
    if registry_type:
        query = query.where(RegistryEntry.registry_type == registry_type)
    result = await db.execute(query)
    return list(result.scalars().all())


async def list_entries(
    db: AsyncSession, limit: int, offset: int, status_filter: Optional[str] = None
) -> tuple[list[RegistryEntry], int]:
    """List registry entries with optional status filter."""
    query = select(RegistryEntry).order_by(RegistryEntry.created_at.desc())
    if status_filter:
        query = query.where(RegistryEntry.status == status_filter)
    total = await db.scalar(select(func.count()).select_from(query.subquery()))
    result = await db.execute(query.limit(limit).offset(offset))
    return list(result.scalars().all()), total or 0


def entry_to_dict(entry: RegistryEntry) -> dict:
    return {
        "id": str(entry.id),
        "registry_type": entry.registry_type,
        "document_number": entry.document_number,
        "status": entry.status,
        "holder_name": entry.holder_name,
        "issuing_country": entry.issuing_country,
        "additional_data": entry.additional_data,
    }
