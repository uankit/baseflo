"""Role-based access control: permission matrix + dependency + decorator.

Per docs/40-features/AUTH.md §3.6.

Two enforcement points:
  1. **Route layer** — `Depends(require_permission(Permission.X))`. 401 if no
     auth, 403 if insufficient role.
  2. **Service layer** — `@requires_permission(Permission.X)` on async methods
     that explicitly receive a `TenantCtx` argument. 403 if insufficient role.

The `(role, permission)` table is the single source of truth; both
enforcement points consult it via `has_permission`.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from enum import StrEnum
from functools import wraps
from typing import ParamSpec, TypeVar

from fastapi import Depends

from app.auth.dependencies import require_tenant
from app.core.context import TenantCtx
from app.core.errors import ForbiddenError, UnauthorizedError
from app.db.models.membership import Role

__all__ = [
    "Permission",
    "has_permission",
    "require_permission",
    "requires_permission",
]


class Permission(StrEnum):
    BILLING_MANAGE = "billing.manage"
    ORG_DELETE = "org.delete"
    TEAM_MANAGE = "team.manage"
    CONNECTOR_MANAGE = "connector.manage"
    PROJECT_READ = "project.read"
    PROJECT_WRITE = "project.write"
    PROJECT_REFINE = "project.refine"
    EXPORT_DATA = "export.data"
    COMMENT_WRITE = "comment.write"
    PII_REVEAL = "pii.reveal"
    API_KEY_MANAGE = "api_key.manage"


_PERMISSIONS: dict[Role, frozenset[Permission]] = {
    Role.OWNER: frozenset(Permission),
    Role.ADMIN: frozenset({
        Permission.TEAM_MANAGE,
        Permission.CONNECTOR_MANAGE,
        Permission.PROJECT_READ,
        Permission.PROJECT_WRITE,
        Permission.PROJECT_REFINE,
        Permission.EXPORT_DATA,
        Permission.COMMENT_WRITE,
        Permission.PII_REVEAL,
        Permission.API_KEY_MANAGE,
    }),
    Role.EDITOR: frozenset({
        Permission.PROJECT_READ,
        Permission.PROJECT_WRITE,
        Permission.PROJECT_REFINE,
        Permission.EXPORT_DATA,
        Permission.COMMENT_WRITE,
    }),
    Role.VIEWER: frozenset({
        Permission.PROJECT_READ,
        Permission.COMMENT_WRITE,
    }),
}


def has_permission(*, role: str | Role | None, permission: Permission) -> bool:
    """Return whether `role` is granted `permission`. Raises if role is unknown."""
    if role is None:
        return False
    role_enum = role if isinstance(role, Role) else Role(role)
    return permission in _PERMISSIONS[role_enum]


# ---------- FastAPI dependency ----------


def require_permission(
    permission: Permission,
) -> Callable[[TenantCtx], TenantCtx]:
    """FastAPI dep that 401s for no auth and 403s for insufficient role."""

    def dep(tenant: TenantCtx = Depends(require_tenant)) -> TenantCtx:
        if not has_permission(role=tenant.role, permission=permission):
            raise ForbiddenError(
                message=(
                    f"Role {tenant.role!r} lacks permission {permission.value!r}."
                ),
                error_code="BF-AUTH-002",
                details={
                    "permission": permission.value,
                    "role": tenant.role,
                },
            )
        return tenant

    return dep


# ---------- Service-layer decorator ----------


P = ParamSpec("P")
T = TypeVar("T")


def requires_permission(
    permission: Permission,
) -> Callable[[Callable[P, Awaitable[T]]], Callable[P, Awaitable[T]]]:
    """Decorator that gates an async service method on a `TenantCtx` arg.

    The decorated function MUST receive a `TenantCtx` somewhere in its args
    or kwargs (any name). The decorator inspects each value at call time and
    uses the first `TenantCtx` instance it finds. Raises BF-AUTH-001 if none
    is present.
    """

    def decorator(
        fn: Callable[P, Awaitable[T]],
    ) -> Callable[P, Awaitable[T]]:
        @wraps(fn)
        async def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            ctx: TenantCtx | None = None
            for value in (*args, *kwargs.values()):
                if isinstance(value, TenantCtx):
                    ctx = value
                    break
            if ctx is None:
                raise UnauthorizedError(
                    "@requires_permission requires a TenantCtx argument.",
                )
            _enforce_or_raise(ctx=ctx, permission=permission)
            return await fn(*args, **kwargs)

        return wrapper

    return decorator


def _enforce_or_raise(*, ctx: TenantCtx, permission: Permission) -> None:
    if has_permission(role=ctx.role, permission=permission):
        return
    raise ForbiddenError(
        message=f"Role {ctx.role!r} lacks permission {permission.value!r}.",
        error_code="BF-AUTH-002",
        details={"permission": permission.value, "role": ctx.role},
    )
