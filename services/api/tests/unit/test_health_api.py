"""Unit tests for the health and readiness endpoints."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


async def test_health_returns_200(client):
    r = await client.get("/api/v1/health")
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "ok"
    assert data["version"] == "0.1.0"
    assert "timestamp" in data


async def test_health_contains_api_service(client):
    r = await client.get("/api/v1/health")
    data = r.json()
    assert "api" in data["services"]
    assert data["services"]["api"] == "ok"


async def test_readiness_returns_200(client):
    """Readiness should return 200 even when deps are unreachable
    (it reports status, not an error code for degraded)."""
    r = await client.get("/api/v1/ready")
    assert r.status_code == 200
    data = r.json()
    assert data["status"] in ("ok", "degraded", "error")
    assert "timestamp" in data
    assert "version" in data


async def test_readiness_has_expected_services(client):
    r = await client.get("/api/v1/ready")
    data = r.json()
    # These should always be present (may be "error" if not running in Docker)
    for svc in ("postgres", "redis", "minio"):
        assert svc in data["services"], f"Service '{svc}' missing from readiness"


async def test_health_has_request_id_header(client):
    r = await client.get("/api/v1/health")
    assert "x-request-id" in r.headers


async def test_readiness_echoes_client_request_id(client):
    custom_id = "test-req-id-12345"
    r = await client.get("/api/v1/ready", headers={"X-Request-ID": custom_id})
    assert r.headers.get("x-request-id") == custom_id
