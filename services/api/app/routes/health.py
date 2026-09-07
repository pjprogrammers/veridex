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

    # PostgreSQL
    try:
        import asyncpg
        conn = await asyncpg.connect(
            host=settings.POSTGRES_HOST,
            port=settings.POSTGRES_PORT,
            database=settings.POSTGRES_DB,
            user=settings.POSTGRES_USER,
            password=settings.POSTGRES_PASSWORD,
        )
        await conn.close()
        services["postgres"] = "ok"
    except Exception:
        services["postgres"] = "error"

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
        client.bucket_exists(settings.MINIO_BUCKET)
        services["minio"] = "ok"
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
