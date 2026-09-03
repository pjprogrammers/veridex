"""VERIDEX API - Health Check Routes"""
from datetime import datetime

import asyncpg
from fastapi import APIRouter

from app.core.config import get_settings
from app.schemas.schemas import HealthStatus

router = APIRouter(prefix="/health", tags=["health"])
settings = get_settings()

VERSION = "0.1.0"


@router.get("", response_model=HealthStatus)
async def health_check():
    """Check health of the API and its dependencies."""
    services = {}

    # PostgreSQL check
    try:
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

    # Redis check
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

    # MinIO check
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
