"""Tenant / user context propagation."""

from __future__ import annotations

from contextvars import ContextVar
from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True, slots=True)
class TenantCtx:
    organization_id: UUID
    user_id: UUID


_tenant_ctx: ContextVar[TenantCtx | None] = ContextVar("tenant_ctx", default=None)


def set_tenant_ctx(ctx: TenantCtx) -> None:
    _tenant_ctx.set(ctx)


def get_tenant_ctx() -> TenantCtx:
    ctx = _tenant_ctx.get()
    if ctx is None:
        raise RuntimeError("Tenant context not set")
    return ctx


def clear_tenant_ctx() -> None:
    _tenant_ctx.set(None)
