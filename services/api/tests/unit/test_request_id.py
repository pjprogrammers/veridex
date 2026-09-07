"""Unit tests for the X-Request-ID middleware."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import uuid

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


async def test_request_id_generated_when_not_supplied(client):
    r = await client.get("/api/v1/health")
    rid = r.headers.get("x-request-id")
    assert rid is not None
    # Should be a valid UUID
    parsed = uuid.UUID(rid)
    assert str(parsed) == rid


async def test_request_id_echoed_back(client):
    custom = "my-custom-request-id-abc"
    r = await client.get("/api/v1/health", headers={"X-Request-ID": custom})
    assert r.headers.get("x-request-id") == custom


async def test_request_id_on_readiness(client):
    r = await client.get("/api/v1/ready")
    assert "x-request-id" in r.headers
    uuid.UUID(r.headers["x-request-id"])  # should not raise


async def test_request_id_on_root(client):
    r = await client.get("/")
    assert "x-request-id" in r.headers
