"""Shared pytest fixtures for DB-backed tests."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.core.database import Base


@pytest.fixture
async def db_session():
    """Create an isolated in-memory async DB session for tests."""
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Reset the global rate limiter between tests so the full suite does not
    # trip the per-minute request budget.
    from app.middleware.rate_limit import RateLimitMiddleware

    RateLimitMiddleware.reset()

    TestingSession = async_sessionmaker(engine, expire_on_commit=False)
    async with TestingSession() as session:
        yield session

    await engine.dispose()
