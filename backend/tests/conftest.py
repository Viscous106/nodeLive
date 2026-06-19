"""Async test fixtures.

Each test gets a clean schema on a dedicated Postgres database (`linkhq_test`)
so behavior matches production (asyncpg + real enums/constraints), not a SQLite
approximation. Engine, sessions, and the HTTP client are all created inside the
test's own event loop to avoid asyncpg "attached to a different loop" errors.
"""

import os
from urllib.parse import urlparse

import asyncpg
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql+asyncpg://edustream:localdev@localhost:5432/linkhq_test",
)


async def _ensure_test_database() -> None:
    """Create the test database if it doesn't exist.

    Lets any dev (and CI) run `pytest` after only `docker compose up postgres` —
    no manual `CREATE DATABASE` step. Connects to the `postgres` maintenance DB
    and creates the target once.
    """
    parsed = urlparse(TEST_DATABASE_URL.replace("postgresql+asyncpg", "postgresql"))
    dbname = parsed.path.lstrip("/")
    admin = await asyncpg.connect(
        host=parsed.hostname,
        port=parsed.port or 5432,
        user=parsed.username,
        password=parsed.password,
        database="postgres",
    )
    try:
        exists = await admin.fetchval(
            "SELECT 1 FROM pg_database WHERE datname = $1", dbname
        )
        if not exists:
            await admin.execute(f'CREATE DATABASE "{dbname}"')
    finally:
        await admin.close()


@pytest_asyncio.fixture
async def engine():
    from app.models import Base  # imports all models → populates metadata

    await _ensure_test_database()
    eng = create_async_engine(TEST_DATABASE_URL)
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield eng
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await eng.dispose()


@pytest_asyncio.fixture
async def session(engine):
    maker = async_sessionmaker(engine, expire_on_commit=False)
    async with maker() as s:
        yield s


@pytest_asyncio.fixture
async def client(engine):
    """HTTP client with get_db overridden to use the test database."""
    from app.db.session import get_db
    from app.main import app

    maker = async_sessionmaker(engine, expire_on_commit=False)

    async def _get_db():
        async with maker() as s:
            yield s

    app.dependency_overrides[get_db] = _get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()
