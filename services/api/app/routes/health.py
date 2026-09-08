"""VERIDEX API - Health & Readiness Routes"""
from datetime import datetime

from fastapi import APIRouter

from app.core.config import get_settings
from app.schemas.schemas import HealthStatus

router = APIRouter(tags=["health"])
settings = get_settings()

VERSION = "0.1.0"


@router.get("/health", response_model=HealthStatus)
async def health_check():
    """Liveness: is the API process alive and able to serve requests."""
    return HealthStatus(
        status="ok",
        version=VERSION,
        services={"api": "ok"},
        timestamp=datetime.utcnow(),
    )


@router.get("/ready", response_model=HealthStatus)
async def readiness_check():
    """Readiness: are all backing dependencies reachable.

    Checks PostgreSQL, Redis, and MinIO.  A degraded status means at
    least one dependency is unreachable but the API is still serving.
    """
    services: dict[str, str] = {}

    # Database. Standalone SQLite mode is supported, so use the configured
    # SQLAlchemy URL instead of assuming PostgreSQL is always active.
    try:
        if settings.database_url.startswith("sqlite"):
            from sqlalchemy import text

            from app.core.database import engine

            async with engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
            services["database"] = "ok"
        else:
            import asyncpg

            conn = await asyncpg.connect(
                dsn=settings.database_url.replace("postgresql+asyncpg://", "postgresql://", 1),
            )
            await conn.close()
            services["postgres"] = "ok"
    except Exception:
        services["database" if settings.database_url.startswith("sqlite") else "postgres"] = "error"

    # Redis
    try:
        import redis
        r = redis.Redis(
            host=settings.REDIS_HOST,
            port=settings.REDIS_PORT,
            db=settings.REDIS_DB,
            socket_connect_timeout=2,
        )
        r.ping()
        services["redis"] = "ok"
    except Exception:
        services["redis"] = "error"

    # MinIO
    try:
        from app.core.storage import get_minio_client
        client = get_minio_client()
        if client.bucket_exists(settings.MINIO_BUCKET):
            services["minio"] = "ok"
        else:
            services["minio"] = "error"
    except Exception:
        services["minio"] = "error"

    degraded = any(v == "error" for v in services.values())
    status = "error" if all(v == "error" for v in services.values()) else (
        "degraded" if degraded else "ok"
    )

    return HealthStatus(
        status=status,
        version=VERSION,
        services=services,
        timestamp=datetime.utcnow(),
    )
