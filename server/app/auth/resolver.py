"""Resolves an inbound request to a `TenantCtx` (or None for unauthenticated).

Per docs/40-features/AUTH.md §3.3. Strategy chain in priority order:

  1. Session cookie + active-org pick from membership.
  2. Local-env dev headers (preserves M0 fixture path).
  3. None — protected routes return 401 via `require_tenant`.

API-key Bearer auth is not available until the issuance route ships (see
Post-Alpha Backlog). When it lands, this chain gets a
new step between (1) and (2). `TenantCtx.is_api_key` + `api_key_id` are
already wired through downstream so no resolver-call-site changes will be
needed at that time.

The resolver is a pure object: pass in fake services to test, real
repositories to run in the middleware. No global state.
"""

from __future__ import annotations

from typing import Protocol
from uuid import UUID

from fastapi import Request

from app.auth.cookies import read_session_cookie
from app.auth.sessions import SessionService
from app.core.config import Environment
from app.core.context import TenantCtx
from app.observability.logging import get_logger
from app.repositories.memberships import ResolvedMembership

__all__ = ["AuthResolver", "MembershipDirectory", "parse_dev_headers"]


logger = get_logger("auth.resolver")


DEV_ORG_HEADER = "X-Baseflo-Org-Id"
DEV_USER_HEADER = "X-Baseflo-User-Id"


def parse_dev_headers(
    *, request: Request, request_id: str,
) -> TenantCtx | None:
    """Return a minimal `TenantCtx` from `X-Baseflo-Org-Id` (+ optional User-Id).

    Honored only in `local` env by the auth middleware; broken out so the
    middleware can run the dev path without opening a DB connection.
    """
    org_raw = request.headers.get(DEV_ORG_HEADER)
    if org_raw is None:
        return None
    try:
        org_id = UUID(org_raw)
    except ValueError:
        return None
    user_id: UUID | None = None
    user_raw = request.headers.get(DEV_USER_HEADER)
    if user_raw is not None:
        try:
            user_id = UUID(user_raw)
        except ValueError:
            user_id = None
    return TenantCtx(
        organization_id=org_id,
        user_id=user_id,
        request_id=request_id,
    )


class MembershipDirectory(Protocol):
    """Service-shaped slice of `MembershipRepository`."""

    async def list_for_user(self, user_id: UUID) -> list[ResolvedMembership]: ...


class AuthResolver:
    ACTIVE_ORG_QUERY = "org"
    ACTIVE_ORG_HEADER = "X-Baseflo-Active-Org"

    def __init__(
        self,
        *,
        sessions: SessionService,
        memberships: MembershipDirectory,
        env: Environment,
    ) -> None:
        self._sessions = sessions
        self._memberships = memberships
        self._env = env

    async def resolve(
        self, *, request: Request, request_id: str,
    ) -> TenantCtx | None:
        ctx = await self._try_session(request, request_id)
        if ctx is not None:
            return ctx
        if self._env == Environment.LOCAL:
            return self._try_dev_headers(request, request_id)
        return None

    # ---------- Session-cookie path ----------

    async def _try_session(
        self, request: Request, request_id: str,
    ) -> TenantCtx | None:
        raw_token = read_session_cookie(request)
        if raw_token is None:
            return None
        resolved = await self._sessions.validate(raw_token)
        if resolved is None:
            return None
        memberships = await self._memberships.list_for_user(resolved.user_id)
        if not memberships:
            logger.info(
                "auth_session_no_memberships",
                user_id=str(resolved.user_id),
                request_id=request_id,
            )
            return None
        active = self._pick_active(request, memberships)
        return TenantCtx(
            organization_id=active.organization_id,
            user_id=resolved.user_id,
            request_id=request_id,
            role=active.role,
            session_id=resolved.session_id,
        )

    def _pick_active(
        self, request: Request, memberships: list[ResolvedMembership],
    ) -> ResolvedMembership:
        slug = request.query_params.get(self.ACTIVE_ORG_QUERY)
        if slug:
            for m in memberships:
                if m.organization_slug == slug:
                    return m
        header = request.headers.get(self.ACTIVE_ORG_HEADER)
        if header:
            try:
                uid = UUID(header)
            except ValueError:
                for m in memberships:
                    if m.organization_slug == header:
                        return m
            else:
                for m in memberships:
                    if m.organization_id == uid:
                        return m
        return sorted(memberships, key=lambda m: m.membership_id)[0]

    # ---------- Local dev-header fallback ----------

    def _try_dev_headers(
        self, request: Request, request_id: str,
    ) -> TenantCtx | None:
        return parse_dev_headers(request=request, request_id=request_id)
