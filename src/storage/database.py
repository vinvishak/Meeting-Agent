"""
Async SQLAlchemy engine and session factory.

Usage:
    async with AsyncSessionLocal() as session:
        result = await session.execute(...)

Or via FastAPI dependency:
    async def endpoint(session: AsyncSession = Depends(get_db)):
        ...
"""

import os
from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from src.config import get_settings

_settings = get_settings()

# Ensure the data directory exists for SQLite
if "sqlite" in _settings.database_url:
    _db_path = _settings.database_url.split("///", 1)[-1]
    _db_dir = os.path.dirname(os.path.abspath(_db_path))
    os.makedirs(_db_dir, exist_ok=True)

engine = create_async_engine(
    _settings.database_url,
    echo=False,
    connect_args={"check_same_thread": False} if "sqlite" in _settings.database_url else {},
)

AsyncSessionLocal: async_sessionmaker[AsyncSession] = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency that yields an async DB session."""
    async with AsyncSessionLocal() as session:
        yield session
