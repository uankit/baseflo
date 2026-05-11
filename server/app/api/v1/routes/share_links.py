"""Share-link endpoints.

Per docs/30-features.md SEC-EXPORT (sharing).

  POST   /api/v1/projects/{id}/share-links     → create a token
  GET    /api/v1/projects/{id}/share-links     → list tokens
  GET    /api/v1/share/{token}                 → verify
  DELETE /api/v1/share-links/{token}           → revoke (idempotent)
"""

from __future__ import annotations

import secrets
from datetime import UTC, datetime, timedelta
from typing import Annotated
from uuid import UUID  # noqa: TC003

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select

from app.auth.dependencies import require_tenant
from app.core.config import get_config
from app.core.context import TenantCtx  # noqa: TC001
from app.core.errors import BasefloError, UnauthorizedError
from app.core.ids import new_uuid7
from app.db.models.audit import ActorType, AuditEvent
from app.db.models.project import Project, ProjectVersion
from app.db.models.sharing import ShareLink
from app.db.models.user import User
from app.db.session import open_session
from app.observability.logging import get_logger
from app.services.sharing import (
    revoke_share_link,
    verify_share_token,
)

router = APIRouter(tags=["share_links"])
logger = get_logger("api.share_links")


class CreateShareLinkRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    version_id: UUID | None = Field(default=None, alias="versionId")
    permissions: str = Field(default="full_read_only")
    expires_in_hours: int | None = Field(default=168, alias="expiresInHours", ge=1)
    ttl_days: int | None = Field(default=None, ge=1, le=365)
    password: str | None = Field(default=None, min_length=4)
    notes: str | None = Field(default=None, max_length=280)


class CreateShareLinkResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    id: UUID
    project_id: UUID = Field(alias="projectId")
    version_id: UUID = Field(alias="versionId")
    token: str
    url: str
    permissions: str
    has_password: bool = Field(alias="hasPassword")
    expires_at: datetime | None = Field(alias="expiresAt")
    notes: str | None
    created_at: datetime = Field(alias="createdAt")
    revoked_at: datetime | None = Field(alias="revokedAt")
    created_by: dict[str, str | None] = Field(alias="createdBy")


class VerifyShareLinkResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    project_id: UUID
    project_version_id: UUID
    expires_at: datetime | None


@router.post(
    "/projects/{project_id}/share-links",
    status_code=status.HTTP_201_CREATED,
    response_model=CreateShareLinkResponse,
    summary="Mint a read-only share token for the project's current version",
)
async def post_share_link(
    project_id: UUID,
    body: CreateShareLinkRequest,
    tenant: Annotated[TenantCtx, Depends(require_tenant)],
) -> CreateShareLinkResponse:
    if tenant.user_id is None:
        raise UnauthorizedError(
            message="Creating a share link requires an authenticated user.",
            error_code="BF-AUTH-001",
        )
    if body.password is not None:
        raise BasefloError(
            error_code="BF-API-005",
            message="Password-protected share links are not enabled for this deployment.",
            status_code=409,
        )
    if body.notes is not None:
        raise BasefloError(
            error_code="BF-API-005",
            message="Share-link notes are not enabled for this deployment.",
            status_code=409,
        )
    if body.permissions not in {"overview_only", "overview_kpis", "full_read_only"}:
        raise BasefloError(
            error_code="BF-VALID-001",
            message="Unsupported share-link permission.",
            status_code=400,
        )

    async with open_session() as session:
        project = await session.get(Project, project_id)
        if project is None or project.organization_id != tenant.organization_id:
            raise BasefloError(
                error_code="BF-API-001",
                message="Project not found.",
                status_code=404,
            )
        version_id = body.version_id or project.current_version_id
        if version_id is None:
            raise BasefloError(
                error_code="BF-API-005",
                message="Project has no current version; cannot share.",
                status_code=400,
            )
        version = await session.get(ProjectVersion, version_id)
        if version is None or version.project_id != project_id:
            raise BasefloError(
                error_code="BF-API-001",
                message="Project version not found.",
                status_code=404,
            )

        expires_at = _expires_at(body)
        row = ShareLink(
            id=new_uuid7(),
            organization_id=tenant.organization_id,
            project_id=project_id,
            project_version_id=version.id,
            token=_new_share_token(),
            permissions=[body.permissions],
            expires_at=expires_at,
            created_by=tenant.user_id,
        )
        session.add(row)
        session.add(
            AuditEvent(
                organization_id=tenant.organization_id,
                actor_type=ActorType.USER.value,
                actor_id=str(tenant.user_id),
                action="share.create",
                target_kind="share_link",
                target_id=str(row.id),
                extra={
                    "project_id": str(project_id),
                    "actor_label": str(tenant.user_id),
                    "target_label": row.token[:8],
                },
            )
        )
        await session.flush()
        await session.refresh(row)
        creator = await session.get(User, tenant.user_id) if tenant.user_id else None
        return _share_link_to_web(
            row, display_name=creator.display_name if creator else None
        )


@router.get(
    "/projects/{project_id}/share-links",
    response_model=list[CreateShareLinkResponse],
    summary="List read-only share links for a project",
)
async def list_share_links(
    project_id: UUID,
    tenant: Annotated[TenantCtx, Depends(require_tenant)],
) -> list[CreateShareLinkResponse]:
    async with open_session() as session:
        project = await session.get(Project, project_id)
        if project is None or project.organization_id != tenant.organization_id:
            raise BasefloError(
                error_code="BF-API-001",
                message="Project not found.",
                status_code=404,
            )
        rows = (
            await session.execute(
                select(ShareLink)
                .where(ShareLink.project_id == project_id)
                .order_by(ShareLink.created_at.desc())
                .limit(100)
            )
        ).scalars().all()
        user_ids = {r.created_by for r in rows if r.created_by is not None}
        names: dict[str, str | None] = {}
        if user_ids:
            name_rows = (
                await session.execute(
                    select(User.id, User.display_name).where(
                        User.id.in_(list(user_ids))
                    )
                )
            ).all()
            names = {str(r[0]): r[1] for r in name_rows}
        return [
            _share_link_to_web(row, display_name=names.get(str(row.created_by)))
            for row in rows
        ]


@router.get(
    "/share/{token}",
    response_model=VerifyShareLinkResponse,
    summary="Verify a share token and return the linked project version",
)
async def get_share(token: str) -> VerifyShareLinkResponse:
    """Public endpoint — no auth. The token IS the credential."""
    result = await verify_share_token(token)
    return VerifyShareLinkResponse(
        project_id=result.project_id,
        project_version_id=result.project_version_id,
        expires_at=result.expires_at,
    )


@router.delete(
    "/share-links/{token}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Revoke a share token (idempotent)",
)
async def delete_share_link(
    token: str, tenant: Annotated[TenantCtx, Depends(require_tenant)],
) -> None:
    await revoke_share_link(token=token, organization_id=tenant.organization_id)


def _expires_at(body: CreateShareLinkRequest) -> datetime | None:
    if body.ttl_days is not None:
        return datetime.now(UTC) + timedelta(days=body.ttl_days)
    if body.expires_in_hours is None:
        return None
    return datetime.now(UTC) + timedelta(hours=body.expires_in_hours)


def _new_share_token() -> str:
    return secrets.token_urlsafe(32)


def _share_link_to_web(
    row: ShareLink, *, display_name: str | None = None
) -> CreateShareLinkResponse:
    permission = row.permissions[0] if row.permissions else "full_read_only"
    web_base = get_config().web_base_url.rstrip("/")
    return CreateShareLinkResponse(
        id=row.id,
        projectId=row.project_id,
        versionId=row.project_version_id,
        token=row.token,
        url=f"{web_base}/s/{row.token}",
        permissions=permission,
        hasPassword=False,
        expiresAt=row.expires_at,
        notes=None,
        createdAt=row.created_at,
        revokedAt=row.revoked_at,
        createdBy={"id": str(row.created_by), "displayName": display_name},
    )
