"""VERIDEX API - Synthetic Data Seeding

Creates realistic-looking but entirely synthetic data for the prototype.
No real personal data is used.

Roles seeded (RBAC, authoritative via users -> user_roles -> roles):
  OFFICER, SUPERVISOR, ADMIN, AUDITOR

Development credentials (synthetic only):
  admin@veridex.local  / VeridexDev123!
  officer1@veridex.local / OfficerDev123!
"""
import asyncio
import random
from datetime import datetime, timedelta

import structlog
from sqlalchemy import func, select

from app.core.database import AsyncSessionLocal, Base, engine
from app.core.security import hash_password
from app.models.models import RegistryEntry, Role, User, VerificationCase, user_roles
from app.services.audit import append_audit_entry

logger = structlog.get_logger()

# ---------------------------------------------------------------------------
# RBAC role definitions (authoritative — roles table)
# ---------------------------------------------------------------------------
ROLE_DEFS: list[dict[str, str | list[str]]] = [
    {
        "name": "OFFICER",
        "description": (
            "Frontline border/checkpoint officer. Can create cases, "
            "upload documents, and run verification."
        ),
        "permissions": [
            "cases:read",
            "cases:create",
            "documents:upload",
            "verification:run",
            "registry:read",
            "audit:read",
        ],
    },
    {
        "name": "SUPERVISOR",
        "description": "Supervisory officer. Can review and override case statuses, view all audit trails.",
        "permissions": [
            "cases:read",
            "cases:create",
            "cases:override",
            "documents:upload",
            "verification:run",
            "registry:read",
            "audit:read",
        ],
    },
    {
        "name": "ADMIN",
        "description": (
            "System administrator. Full access to all features "
            "including registry management and user administration."
        ),
        "permissions": [
            "cases:read",
            "cases:create",
            "cases:delete",
            "cases:override",
            "documents:upload",
            "verification:run",
            "registry:read",
            "registry:write",
            "audit:read",
            "users:admin",
        ],
    },
    {
        "name": "AUDITOR",
        "description": "Read-only auditor. Can inspect cases, audit trails, and verify chain integrity.",
        "permissions": [
            "cases:read",
            "registry:read",
            "audit:read",
        ],
    },
]

# Synthetic user definitions (development only)
SEED_USERS = [
    {
        "username": "admin",
        "email": "admin@veridex.local",
        "password": "VeridexDev123!",
        "full_name": "System Administrator",
        "role": "admin",  # legacy string column
        "rbac_role": "ADMIN",
    },
    {
        "username": "officer1",
        "email": "officer1@veridex.local",
        "password": "OfficerDev123!",
        "full_name": "Officer Sample",
        "role": "officer",
        "rbac_role": "OFFICER",
    },
    {
        "username": "supervisor1",
        "email": "supervisor1@veridex.local",
        "password": "SupervisorDev123!",
        "full_name": "Supervisor Sample",
        "role": "officer",  # legacy column; RBAC is authoritative
        "rbac_role": "SUPERVISOR",
    },
    {
        "username": "auditor1",
        "email": "auditor1@veridex.local",
        "password": "AuditorDev123!",
        "full_name": "Auditor Sample",
        "role": "officer",
        "rbac_role": "AUDITOR",
    },
]

FIRST_NAMES = ["Alex", "Jordan", "Morgan", "Casey", "Riley", "Taylor", "Avery", "Quinn", "Remy"]
LAST_NAMES = ["Doe", "Smith", "Johnson", "Chen", "Patel", "Kim", "Nakamura", "Garcia", "Silva", "Okafor"]
COUNTRIES = ["US", "GB", "CA", "AU", "IN", "JP", "DE", "FR", "BR", "NG"]

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


async def _seed_roles(db) -> dict[str, Role]:
    """Seed RBAC roles and return a name->Role mapping."""
    existing = await db.execute(select(Role))
    existing_names = {r.name for r in existing.scalars().all()}
    role_map: dict[str, Role] = {}

    for defn in ROLE_DEFS:
        name = str(defn["name"])
        if name in existing_names:
            # Already seeded — fetch for the map
            result = await db.execute(select(Role).where(Role.name == name))
            role_map[name] = result.scalar_one()
        else:
            role = Role(
                name=name,
                description=str(defn["description"]),
                permissions=list(defn["permissions"]),
            )
            db.add(role)
            await db.flush()
            role_map[name] = role
            logger.info("role_created", role_name=name)

    return role_map


async def _seed_users(db, role_map: dict[str, Role]) -> None:
    """Seed synthetic users and assign RBAC roles."""
    existing = await db.execute(select(User.username))
    existing_names = {u for (u,) in existing}

    for spec in SEED_USERS:
        if spec["username"] in existing_names:
            continue
        user = User(
            username=spec["username"],
            email=spec["email"],
            hashed_password=hash_password(spec["password"]),
            full_name=spec["full_name"],
            role=spec["role"],
        )
        db.add(user)
        await db.flush()
        # Assign RBAC role via junction table
        rbac_role = role_map.get(spec["rbac_role"])
        if rbac_role:
            await db.execute(
                user_roles.insert().values(user_id=user.id, role_id=rbac_role.id)
            )
        logger.info("user_created", username=spec["username"], rbac_role=spec["rbac_role"])

    existing_names_after = {u for (u,) in (await db.execute(select(User.username)))}
    logger.info("users_seeded", total=len(existing_names_after))


async def _seed_registry(db) -> None:
    count = await db.scalar(select(func.count()).select_from(RegistryEntry))
    if count and count > 0:
        return

    entries = []
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
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with AsyncSessionLocal() as db:
        role_map = await _seed_roles(db)
        await _seed_users(db, role_map)
        await _seed_registry(db)
        await _seed_demo_cases(db)
        await db.commit()


if __name__ == "__main__":
    asyncio.run(seed_database())
    print("Database seeded successfully.")
