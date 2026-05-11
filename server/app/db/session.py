"""Async database session management."""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import get_settings

_settings = get_settings()

DATABASE_URL = str(_settings.database_url)

engine = create_async_engine(
    DATABASE_URL,
    echo=_settings.database_echo,
    pool_pre_ping=True,
)

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)


@asynccontextmanager
async def open_session() -> AsyncIterator[AsyncSession]:
    """Yield a transactional session."""
    async with AsyncSessionLocal() as session:
        async with session.begin():
            yield session
