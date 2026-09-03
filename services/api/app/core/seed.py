"""VERIDEX API - Synthetic Data Seeding

This module creates realistic-looking but entirely synthetic data
for the prototype. No real personal data is used.
"""
import asyncio
import random
from datetime import datetime, timedelta

import structlog
from sqlalchemy import func, select

from app.core.database import AsyncSessionLocal, Base, engine
from app.core.security import hash_password
from app.models.models import RegistryEntry, User, VerificationCase
from app.services.audit import append_audit_entry

logger = structlog.get_logger()


FIRST_NAMES = ["Alex", "Jordan", "Morgan", "Casey", "Riley", "Taylor", "Jordan", "Avery", "Quinn", "Remy"]
LAST_NAMES = ["Doe", "Smith", "Johnson", "Chen", "Patel", "Kim", "Nakamura", "Garcia", "Silva", "Okafor"]
COUNTRIES = ["US", "GB", "CA", "AU", "IN", "JP", "DE", "FR", "BR", "NG"]

# Known document numbers referenced by scripts/synthetic_documents.py and the
# frontend registry lookup demo. Kept stable so demo data lines up.
KNOWN_DOCS = {
    "passport": {
        "number": "P12345678",
        "holder": "Jordan Smith",
        "country": "GB",
        "status": "valid",
    },
    "national_id": {
        "number": "N87654321",
        "holder": "Alex Johnson",
        "country": "IN",
        "status": "reported_stolen",
    },
    "blacklist": {
        "number": "B55544433",
        "holder": "Morgan Chen",
        "country": "US",
        "status": "blacklisted",
    },
}


def _doc_number():
    return f"{random.choice('ABCDEFGHJKMNPQRSTUVWXYZ')}{random.randint(100000, 999999)}"


async def _seed_registry(db) -> None:
    count = await db.scalar(select(func.count()).select_from(RegistryEntry))
    if count and count > 0:
        return

    entries = []
    # Known demo documents
    for entry in KNOWN_DOCS.values():
        entries.append(
            RegistryEntry(
                registry_type=random.choice(["passport", "national_id", "immigration"]),
                document_number=entry["number"],
                status=entry["status"],
                holder_name=entry["holder"],
                issuing_country=entry["country"],
            )
        )
    # Random synthetic entries
    for _ in range(200):
        entries.append(
            RegistryEntry(
                registry_type=random.choice(["immigration", "national_id", "passport"]),
                document_number=_doc_number(),
                status=random.choices(
                    ["valid", "valid", "valid", "reported_stolen", "blacklisted", "expired"],
                    weights=[50, 15, 15, 10, 5, 5],
                )[0],
                holder_name=f"{random.choice(FIRST_NAMES)} {random.choice(LAST_NAMES)}",
                issuing_country=random.choice(COUNTRIES),
            )
        )
    db.add_all(entries)
    logger.info("seeded_registry", count=len(entries))


async def _seed_demo_cases(db) -> None:
    """Create a couple of demo cases with risk/audit data for the dashboard."""
    existing = await db.scalar(
        select(func.count()).select_from(VerificationCase)
    )
    if existing and existing > 0:
        return

    officer = await db.scalar(select(User).where(User.username == "officer1"))

    demo = [
        {
            "case_number": "VRX-2026-000001",
            "description": "Synthetic traveler passport check at border checkpoint",
            "status": "flagged",
            "risk_level": "HIGH",
            "risk_score": 0.78,
            "days_ago": 1,
            "created_by": officer.id if officer else None,
            "actions": [("case_created", {"case_number": "VRX-2026-000001"})],
        },
        {
            "case_number": "VRX-2026-000002",
            "description": "National identity verification for domestic flight",
            "status": "under_examination",
            "risk_level": "LOW",
            "risk_score": 0.12,
            "days_ago": 3,
            "created_by": officer.id if officer else None,
            "actions": [("case_created", {"case_number": "VRX-2026-000002"})],
        },
    ]

    for spec in demo:
        case = VerificationCase(
            case_number=spec["case_number"],
            description=spec["description"],
            status=spec.get("status", "in_review"),
            risk_level=spec.get("risk_level"),
            risk_score=spec.get("risk_score"),
            created_by=spec["created_by"],
            created_at=datetime.utcnow() - timedelta(days=spec["days_ago"]),
            updated_at=datetime.utcnow() - timedelta(days=spec["days_ago"]),
            case_metadata={"check_registry": True, "perform_forensics": True},
        )
        db.add(case)
        await db.flush()
        for action, payload in spec["actions"]:
            await append_audit_entry(
                db,
                case_id=case.id,
                action=action,
                actor_id=spec["created_by"],
                actor_role=officer.role if officer else "officer",
                payload=payload,
            )
    logger.info("seeded_demo_cases", count=len(demo))


async def seed_database():
    """Seed the database with synthetic data."""
    # Create tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with AsyncSessionLocal() as db:
        # Seed admin user
        existing = await db.execute(select(User).where(User.username == "admin"))
        if not existing.scalar_one_or_none():
            admin = User(
                username="admin",
                email="admin@synthetic.veridex.local",
                hashed_password=hash_password("Admin123!"),
                full_name="System Administrator",
                role="admin",
            )
            officer = User(
                username="officer1",
                email="officer1@synthetic.veridex.local",
                hashed_password=hash_password("Officer123!"),
                full_name="Officer Sample",
                role="officer",
            )
            db.add_all([admin, officer])
            await db.flush()
            logger.info("seeded_users")

        await _seed_registry(db)
        await _seed_demo_cases(db)
        await db.commit()


if __name__ == "__main__":
    asyncio.run(seed_database())
    print("Database seeded successfully.")


if __name__ == "__main__":
    asyncio.run(seed_database())
    print("Database seeded successfully.")
