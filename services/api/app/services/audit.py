"""Tamper-evident audit trail service.

Creates SHA-256-chained audit entries: each entry's hash covers the previous
entry's hash, so altering any historical entry breaks the chain and is
detectable. Only metadata and hashes are recorded — never raw images or PII
payload contents beyond minimal action metadata.
"""
import hashlib
import json
from typing import Any, Optional

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.models import AuditLog

logger = structlog.get_logger()


def _canonical_payload(entry_fields: dict) -> bytes:
    """Serialize entry content deterministically for hashing."""
    return json.dumps(entry_fields, sort_keys=True, default=str).encode("utf-8")


def compute_entry_hash(
    *,
    entry_id: Optional[int],
    case_id: Any,
    action: str,
    actor_id: Any,
    actor_role: Optional[str],
    timestamp: Any,
    previous_hash: Optional[str],
    payload: dict,
) -> str:
    """Compute the SHA-256 hash of an audit entry's content."""
    entry_fields = {
        "id": entry_id,
        "case_id": str(case_id) if case_id is not None else None,
        "action": action,
        "actor_id": str(actor_id) if actor_id is not None else None,
        "actor_role": actor_role,
        "timestamp": str(timestamp) if timestamp is not None else None,
        "previous_hash": previous_hash,
        "payload": payload,
    }
    return hashlib.sha256(_canonical_payload(entry_fields)).hexdigest()


async def append_audit_entry(
    db: AsyncSession,
    *,
    case_id: Any,
    action: str,
    actor_id: Any,
    actor_role: Optional[str],
    payload: Optional[dict] = None,
) -> AuditLog:
    """Append a new entry to the audit chain and return it."""
    # Find the latest entry hash to chain from.
    last = await db.scalar(
        select(AuditLog)
        .where(AuditLog.case_id == case_id)
        .order_by(AuditLog.id.desc())
        .limit(1)
    )
    previous_hash = last.current_hash if last else None

    entry = AuditLog(
        case_id=case_id,
        action=action,
        actor_id=actor_id,
        actor_role=actor_role,
        previous_hash=previous_hash,
        payload=payload or {},
        current_hash="",  # placeholder, set below
    )
    db.add(entry)
    await db.flush()  # assign id

    entry.current_hash = compute_entry_hash(
        entry_id=entry.id,
        case_id=case_id,
        action=action,
        actor_id=actor_id,
        actor_role=actor_role,
        timestamp=entry.timestamp,
        previous_hash=previous_hash,
        payload=payload or {},
    )
    await db.flush()
    logger.info(
        "audit_entry_created",
        case_id=str(case_id),
        action=action,
        entry_id=entry.id,
    )
    return entry


async def verify_chain(db: AsyncSession, case_id: Any) -> dict:
    """Verify the integrity of the audit chain for a case."""
    entries = (
        await db.execute(
            select(AuditLog)
            .where(AuditLog.case_id == case_id)
            .order_by(AuditLog.id.asc())
        )
    ).scalars().all()

    issues = []
    for i, entry in enumerate(entries):
        recomputed = compute_entry_hash(
            entry_id=entry.id,
            case_id=entry.case_id,
            action=entry.action,
            actor_id=entry.actor_id,
            actor_role=entry.actor_role,
            timestamp=entry.timestamp,
            previous_hash=entry.previous_hash,
            payload=entry.payload,
        )
        if recomputed != entry.current_hash:
            issues.append({"entry_id": entry.id, "reason": "hash_mismatch"})
        if i > 0 and entry.previous_hash != entries[i - 1].current_hash:
            issues.append({"entry_id": entry.id, "reason": "broken_chain"})

    return {
        "case_id": str(case_id),
        "valid": len(issues) == 0,
        "total_entries": len(entries),
        "integrity_issues": issues,
    }
