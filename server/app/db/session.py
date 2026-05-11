"""Async SQLAlchemy session management + tenant-scoped session helpers.

Per docs/05-coding-rules.md §4 the engine is async; per §3.2 only repositories
talk to sessions.

Tenant scoping for RLS: at the start of each request that has a `TenantCtx`,
we issue `SET LOCAL app.organization_id = '<uuid>'`. RLS policies on every
multi-tenant table enforce equality with this session var.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.sql import text

from app.core.config import get_config
from app.core.context import try_get_tenant_ctx


def _make_engine() -> AsyncEngine:
    config = get_config()
    return create_async_engine(
        config.database_url,
        echo=False,
        future=True,
        pool_size=config.database_pool_size,
        max_overflow=config.database_max_overflow,
        pool_pre_ping=True,
    )


_engine: AsyncEngine | None = None
_session_maker: async_sessionmaker[AsyncSession] | None = None


def get_engine() -> AsyncEngine:
    global _engine
    if _engine is None:
        _engine = _make_engine()
    return _engine


def get_session_maker() -> async_sessionmaker[AsyncSession]:
    global _session_maker
    if _session_maker is None:
        _session_maker = async_sessionmaker(
            bind=get_engine(),
            expire_on_commit=False,
            autoflush=False,
            class_=AsyncSession,
        )
    return _session_maker


async def reset_engine_for_tests() -> None:
    """Dispose engine + session maker. Called by test fixtures."""
    global _engine, _session_maker
    if _engine is not None:
        await _engine.dispose()
    _engine = None
    _session_maker = None


@asynccontextmanager
async def open_session() -> AsyncIterator[AsyncSession]:
    """Open an async session and apply the tenant RLS scope if available.

    Use this from request handlers and job runners. Repositories receive
    the resulting `AsyncSession` via DI; they do not call this helper.
    """
    maker = get_session_maker()
    async with maker() as session:
        ctx = try_get_tenant_ctx()
        if ctx is not None:
            # SET LOCAL is transaction-scoped; safe inside a session.
            await session.execute(
                text("SELECT set_config('app.organization_id', :org_id, true)"),
                {"org_id": str(ctx.organization_id)},
            )
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        else:
            await session.commit()
