"""VERIDEX API - Main Application"""
import structlog
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core.config import get_settings
from app.core.database import init_db
from app.core.logging import setup_logging
from app.middleware.logging import RequestLoggingMiddleware
from app.middleware.rate_limit import RateLimitMiddleware
from app.middleware.request_id import RequestIDMiddleware
from app.routes import audit, auth, cases, documents, health, ocr, registry, verification

settings = get_settings()
setup_logging()
logger = structlog.get_logger()

app = FastAPI(
    title="VERIDEX API",
    description="AI-Powered Fake Identity & Document Screening System",
    version="0.1.0",
    docs_url="/docs",
    openapi_url="/openapi.json",
)

# Middleware — order matters: outermost runs first on request, last on response.
# 1. Request ID (outermost — ensures every log line has the ID)
app.add_middleware(RequestIDMiddleware)
# 2. CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Request-ID"],
)
# 3. Request logging
app.add_middleware(RequestLoggingMiddleware)
# 4. Rate limiting
app.add_middleware(RateLimitMiddleware)


# ---------------------------------------------------------------------------
# Global error handler — never leak internals
# ---------------------------------------------------------------------------
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    request_id = request.headers.get("x-request-id", "unknown")
    logger.error("unhandled_exception", error=str(exc), request_id=request_id, exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "error": {
                "code": "INTERNAL_SERVER_ERROR",
                "message": "An unexpected error occurred",
                "request_id": request_id,
            }
        },
    )


# Import models to ensure they're registered with Base.metadata
from app.models import models  # noqa: E402,F401

# Routes — all under /api/v1
app.include_router(health.router, prefix="/api/v1")
app.include_router(auth.router, prefix="/api/v1")
app.include_router(cases.router, prefix="/api/v1")
app.include_router(registry.router, prefix="/api/v1")
app.include_router(audit.router, prefix="/api/v1")
app.include_router(verification.router, prefix="/api/v1")
app.include_router(documents.router, prefix="/api/v1")
app.include_router(ocr.router, prefix="/api/v1")


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
        "health": "/api/v1/health",
    }
