"""Async SQLAlchemy engine + session factory + FastAPI dependency.

Importing this module does NOT open a database connection — asyncpg only
connects on first query, so the app process and `from app.main import app`
stay cheap. Use `Depends(get_db)` in routes to get a scoped AsyncSession.
"""

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import settings

engine = create_async_engine(
    settings.DATABASE_URL,
    pool_size=10,
    max_overflow=5,
    pool_pre_ping=True,
    echo=settings.DEBUG and settings.ENV == "development",
)

AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Yield a session scoped to one request; always closed afterwards."""
    async with AsyncSessionLocal() as session:
        yield session
