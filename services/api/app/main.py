"""VERIDEX API - Main Application"""
import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings
from app.core.database import init_db
from app.core.logging import setup_logging
from app.middleware.logging import RequestLoggingMiddleware
from app.middleware.rate_limit import RateLimitMiddleware
from app.routes import audit, auth, cases, health, registry, verification

settings = get_settings()
setup_logging()
logger = structlog.get_logger()

app = FastAPI(
    title="VERIDEX API",
    description="AI-Powered Fake Identity & Document Screening System",
    version="0.1.0",
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Custom middleware
app.add_middleware(RequestLoggingMiddleware)
app.add_middleware(RateLimitMiddleware)

# Import models to ensure they're registered
from app.models import models  # noqa: E402,F401

# Routes
app.include_router(health.router)
app.include_router(auth.router, prefix="/api/v1")
app.include_router(cases.router, prefix="/api/v1")
app.include_router(registry.router, prefix="/api/v1")
app.include_router(audit.router, prefix="/api/v1")
app.include_router(verification.router, prefix="/api/v1")


@app.on_event("startup")
async def startup_event():
    await init_db()
    logger.info("application_started", app=settings.APP_NAME, env=settings.APP_ENV)


@app.get("/")
async def root():
    return {
        "app": settings.APP_NAME,
        "version": "0.1.0",
        "docs": "/docs",
        "health": "/health",
    }
