"""Request-scoped context propagation.

ContextVars carry tenant/request/job/agent identity across async boundaries
without needing to thread them through every function signature.

Set by:
- Auth middleware: `tenant_id`, `user_id`, `request_id` per HTTP request.
- Job runner: `job_id`, `tenant_id` per arq job.
- Agent runtime: `agent_run_id`, `agent_name` per agent invocation.

Read by:
- Logger processors (PII scrub + auto-tagging).
- OpenTelemetry span attributes.
- Repository session-var setter for RLS.

These are CONTEXTVARS, not globals: they propagate naturally across `await`
points and isolate concurrent requests within a single worker process.
"""

from __future__ import annotations

from contextvars import ContextVar
from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True, slots=True)
class TenantCtx:
    """The active tenant context for a request, job, or agent run.

    Frozen so it cannot be mutated mid-request (mutation would be a security bug).
    """

    organization_id: UUID
    user_id: UUID | None  # None for system / API-key actors with no user binding
    request_id: str
    role: str | None = None
    """Membership role for the active org: owner / admin / editor / viewer.
    None for the dev-header path (which doesn't authenticate a real membership)
    and for API-key actors whose role lives on the api_key row.
    """
    session_id: UUID | None = None
    """`sessions.id` for cookie-authenticated requests; None otherwise."""
    is_api_key: bool = False
    api_key_id: UUID | None = None


_tenant_ctx: ContextVar[TenantCtx | None] = ContextVar("baseflo_tenant_ctx", default=None)
_job_id: ContextVar[UUID | None] = ContextVar("baseflo_job_id", default=None)
_agent_run_id: ContextVar[UUID | None] = ContextVar("baseflo_agent_run_id", default=None)
_agent_name: ContextVar[str | None] = ContextVar("baseflo_agent_name", default=None)


def get_tenant_ctx() -> TenantCtx:
    """Return the active tenant context, raising if not set.

    Use `try_get_tenant_ctx` if absence is acceptable (e.g., in pre-auth code).
    """
    ctx = _tenant_ctx.get()
    if ctx is None:
        raise LookupError("No TenantCtx set; this code path requires authentication.")
    return ctx


def try_get_tenant_ctx() -> TenantCtx | None:
    return _tenant_ctx.get()


def set_tenant_ctx(ctx: TenantCtx) -> None:
    _tenant_ctx.set(ctx)


def clear_tenant_ctx() -> None:
    _tenant_ctx.set(None)


def get_request_id() -> str | None:
    ctx = _tenant_ctx.get()
    return ctx.request_id if ctx is not None else None


def get_job_id() -> UUID | None:
    return _job_id.get()


def set_job_id(job_id: UUID | None) -> None:
    _job_id.set(job_id)


def get_agent_run_id() -> UUID | None:
    return _agent_run_id.get()


def set_agent_run_id(agent_run_id: UUID | None) -> None:
    _agent_run_id.set(agent_run_id)


def get_agent_name() -> str | None:
    return _agent_name.get()


def set_agent_name(name: str | None) -> None:
    _agent_name.set(name)
