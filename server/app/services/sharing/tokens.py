"""Share-link token service.

Per docs/30-features.md SEC-EXPORT (sharing). This service:

  - `create_share_link(...)` — generate a 32-byte URL-safe random token,
    persist into `share_links` with TTL.
  - `verify_share_token(...)` — look up by token; reject if revoked or
    expired.
  - `revoke_share_link(...)` — mark `revoked_at`.

Pure orchestration over the existing `ShareLink` ORM model.
"""

from __future__ import annotations

import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID  # noqa: TC003

from sqlalchemy import select, text

from app.core.errors import BasefloError
from app.db.models.sharing import ShareLink
from app.db.session import open_session
from app.observability.logging import get_logger

__all__ = [
    "ShareLinkResult",
    "create_share_link",
    "revoke_share_link",
    "verify_share_token",
]


logger = get_logger("services.sharing.tokens")


_TOKEN_BYTES = 32
"""32 random bytes → 43-char URL-safe string. Plenty for unguessability."""

_DEFAULT_TTL_DAYS = 30


@dataclass(frozen=True, slots=True)
class ShareLinkResult:
    """Returned to the user after a successful create/verify."""

    token: str
    organization_id: UUID
    project_id: UUID
    project_version_id: UUID
    expires_at: datetime | None


async def create_share_link(
    *,
    organization_id: UUID,
    project_id: UUID,
    project_version_id: UUID,
    created_by: UUID,
    ttl_days: int = _DEFAULT_TTL_DAYS,
    permissions: list[str] | None = None,
) -> ShareLinkResult:
    """Mint a new share token. Returns the plain token (caller is responsible
    for displaying it once and never persisting it elsewhere)."""
    token = secrets.token_urlsafe(_TOKEN_BYTES)
    expires_at = (
        datetime.now(UTC) + timedelta(days=int(ttl_days))
        if ttl_days > 0
        else None
    )
    async with open_session() as session:
        await session.execute(
            text("SELECT set_config('app.organization_id', :org, true)"),
            {"org": str(organization_id)},
        )
        row = ShareLink(
            organization_id=organization_id,
            project_id=project_id,
            project_version_id=project_version_id,
            token=token,
            permissions=permissions or ["read"],
            expires_at=expires_at,
            created_by=created_by,
        )
        session.add(row)
        await session.flush()

    logger.info(
        "share_link_created",
        project_id=str(project_id),
        project_version_id=str(project_version_id),
        expires_at=expires_at.isoformat() if expires_at else None,
    )
    return ShareLinkResult(
        token=token,
        organization_id=organization_id,
        project_id=project_id,
        project_version_id=project_version_id,
        expires_at=expires_at,
    )


async def verify_share_token(token: str) -> ShareLinkResult:
    """Look up a token and return the link metadata. Raises if revoked /
    expired / unknown — the API surfaces typed BF-API-001 in those cases."""
    async with open_session() as session:
        await session.execute(
            text("SELECT set_config('app.share_token', :token, true)"),
            {"token": token},
        )
        row = (
            await session.execute(
                select(ShareLink).where(ShareLink.token == token)
            )
        ).scalar_one_or_none()

    if row is None:
        raise BasefloError(
            error_code="BF-API-001",
            message="Share token not found.",
            status_code=404,
        )
    if row.revoked_at is not None:
        raise BasefloError(
            error_code="BF-API-001",
            message="Share token has been revoked.",
            status_code=410,
        )
    if row.expires_at is not None and row.expires_at < datetime.now(UTC):
        raise BasefloError(
            error_code="BF-API-001",
            message="Share token has expired.",
            status_code=410,
        )
    return ShareLinkResult(
        token=row.token,
        organization_id=row.organization_id,
        project_id=row.project_id,
        project_version_id=row.project_version_id,
        expires_at=row.expires_at,
    )


async def revoke_share_link(*, token: str, organization_id: UUID) -> None:
    """Mark a share link as revoked. Idempotent."""
    async with open_session() as session:
        await session.execute(
            text("SELECT set_config('app.organization_id', :org, true)"),
            {"org": str(organization_id)},
        )
        row = (
            await session.execute(select(ShareLink).where(ShareLink.token == token))
        ).scalar_one_or_none()
        if row is None or row.revoked_at is not None:
            return
        row.revoked_at = datetime.now(UTC)
        await session.flush()
    logger.info("share_link_revoked", token_prefix=token[:8])
