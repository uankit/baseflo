"""Per-tenant async concurrency control for the agent runtime.

Per docs/40-features/ENG-RUNTIME.md §3.6, one tenant cannot starve others.
Independent specialists run in parallel up to `BASEFLO_AGENT_MAX_CONCURRENCY`.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from uuid import UUID

from app.core.config import get_config


class PerTenantSemaphore:
    """Async semaphore allocator keyed by `organization_id`.

    Lazily creates a semaphore on first use per tenant. Semaphores are not
    persisted; they're an in-process construct. Multi-instance fairness is
    enforced at the job-queue layer (arq) — see docs/40-features/JOBS-AND-SSE.md.
    """

    def __init__(self, max_concurrency: int | None = None) -> None:
        self._max = max_concurrency or get_config().agent_max_concurrency
        self._semaphores: dict[UUID, asyncio.Semaphore] = {}
        self._lock = asyncio.Lock()

    async def _semaphore_for(self, tenant_id: UUID) -> asyncio.Semaphore:
        if tenant_id in self._semaphores:
            return self._semaphores[tenant_id]
        async with self._lock:
            if tenant_id not in self._semaphores:
                self._semaphores[tenant_id] = asyncio.Semaphore(self._max)
            return self._semaphores[tenant_id]

    @asynccontextmanager
    async def acquire(self, tenant_id: UUID) -> AsyncIterator[None]:
        sem = await self._semaphore_for(tenant_id)
        await sem.acquire()
        try:
            yield
        finally:
            sem.release()


_default_semaphore: PerTenantSemaphore | None = None


def get_default_semaphore() -> PerTenantSemaphore:
    global _default_semaphore
    if _default_semaphore is None:
        _default_semaphore = PerTenantSemaphore()
    return _default_semaphore


def reset_default_semaphore() -> None:
    """Test-only."""
    global _default_semaphore
    _default_semaphore = None
