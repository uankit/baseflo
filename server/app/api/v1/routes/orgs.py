"""Organization + project bootstrap routes.

Per `40-features/AUTH.md` (membership) and `04-database-schema.md` §10. Used
by a freshly-signed-in user to create their first organization, and by users
who already have an active tenant context to spin up new projects under it.

  POST /api/v1/orgs              — bootstrap org + default workspace + Owner
                                    membership (uses `require_user`, no
                                    tenant context needed yet).
  POST /api/v1/projects          — create a project under the active org.
  GET  /api/v1/projects/{id}     — fetch one project (RLS-scoped).

Note on RLS for org creation: `organizations` has policy `id = current_setting
('app.organization_id')`. We pre-set the session var to the new org's UUID7
*before* INSERT so both `USING` and `WITH CHECK` pass.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import require_tenant, require_user
from app.auth.magic_link import UserHandle
from app.core.context import TenantCtx
from app.core.errors import BasefloError, NotFoundError, ValidationError
from app.core.ids import new_uuid7
from app.db.models.membership import Membership, Role
from app.db.models.organization import Organization, OrganizationPlan, OrganizationStatus
from app.db.models.project import DeploymentMode, Project
from app.db.models.workspace import Workspace
from app.db.session import open_session
from app.observability.logging import get_logger
from app.repositories.memberships import MembershipRepository, ResolvedMembership


__all__ = [
    "CreateOrgRequest",
    "CreateOrgResponse",
    "CreateProjectRequest",
    "CreateProjectResponse",
    "ProjectSummary",
    "router",
]


router = APIRouter(tags=["orgs"])
logger = get_logger("api.orgs")


# ---------- DB session dep (separate from connectors.py to avoid cross-import) ----------


async def get_db_session() -> AsyncIterator[AsyncSession]:
    async with open_session() as session:
        yield session


# ---------- Request / response models ----------


_SLUG_PATTERN = r"^[a-z0-9](?:[a-z0-9-]{0,78}[a-z0-9])?$"


class CreateOrgRequest(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    slug: str = Field(min_length=2, max_length=80, pattern=_SLUG_PATTERN)


class CreateOrgResponse(BaseModel):
    organization_id: UUID
    workspace_id: UUID
    membership_id: UUID
    slug: str
    role: str


class CreateProjectRequest(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    slug: str = Field(min_length=2, max_length=80, pattern=_SLUG_PATTERN)
    description: str | None = Field(default=None, max_length=2000)
    workspace_id: UUID | None = None
    """If omitted, uses the org's first (default) workspace."""
    deployment_mode: str = Field(default=DeploymentMode.HOSTED.value)


class CreateProjectResponse(BaseModel):
    project_id: UUID
    workspace_id: UUID
    slug: str


class ProjectSummary(BaseModel):
    id: UUID
    organization_id: UUID
    workspace_id: UUID
    name: str
    slug: str
    description: str | None
    deployment_mode: str
    current_version_id: UUID | None
    tenant_data_schema_name: str | None
    currency: str
    created_at: datetime


# ---------- POST /orgs ----------


@router.post(
    "/orgs",
    status_code=201,
    response_model=CreateOrgResponse,
    summary="Bootstrap a new organization with a default workspace",
)
async def create_org(
    body: CreateOrgRequest,
    user: Annotated[UserHandle, Depends(require_user)],
) -> CreateOrgResponse:
    """First-time onboarding: signed-in user with no orgs creates one.

    The caller is made the Owner. A `Default` workspace is auto-created so
    subsequent project creation has somewhere to land without a second call.
    """
    org_id = new_uuid7()
    workspace_id = new_uuid7()
    membership_id = new_uuid7()

    async with open_session() as session:
        # RLS on organizations is `id = current_setting('app.organization_id')`.
        # Pre-set the session var to the new id so the INSERT's WITH CHECK passes.
        await session.execute(
            text("SELECT set_config('app.organization_id', :id, true)"),
            {"id": str(org_id)},
        )
        try:
            session.add(Organization(
                id=org_id,
                name=body.name,
                slug=body.slug,
                plan=OrganizationPlan.HOBBY.value,
                status=OrganizationStatus.ACTIVE.value,
            ))
            await session.flush()
        except IntegrityError as exc:
            raise BasefloError(
                error_code="BF-VALID-009",
                message=f"Organization slug {body.slug!r} is already taken.",
                status_code=409,
                cause=exc,
            ) from exc

        session.add_all([
            Membership(
                id=membership_id,
                organization_id=org_id,
                user_id=user.id,
                role=Role.OWNER.value,
                accepted_at=datetime.now(UTC),
            ),
            Workspace(
                id=workspace_id,
                organization_id=org_id,
                name="Default",
                slug="default",
                created_by=user.id,
            ),
        ])
        await session.flush()

    logger.info(
        "organization_created",
        organization_id=str(org_id),
        slug=body.slug,
        creator_user_id=str(user.id),
    )
    return CreateOrgResponse(
        organization_id=org_id,
        workspace_id=workspace_id,
        membership_id=membership_id,
        slug=body.slug,
        role=Role.OWNER.value,
    )


# ---------- POST /projects ----------


@router.post(
    "/projects",
    status_code=201,
    response_model=CreateProjectResponse,
    summary="Create a project in the active org's (default or specified) workspace",
)
async def create_project(
    body: CreateProjectRequest,
    tenant: Annotated[TenantCtx, Depends(require_tenant)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> CreateProjectResponse:
    if body.deployment_mode not in {dm.value for dm in DeploymentMode}:
        raise ValidationError(
            message=f"Unknown deployment_mode {body.deployment_mode!r}.",
        )
    if tenant.user_id is None:
        # API-key actors cannot create projects.
        raise ValidationError(
            message="Project creation requires a user-authenticated session.",
        )

    workspace_id = body.workspace_id
    if workspace_id is None:
        stmt = (
            select(Workspace)
            .where(
                Workspace.organization_id == tenant.organization_id,
                Workspace.deleted_at.is_(None),
            )
            .order_by(Workspace.created_at)
            .limit(1)
        )
        result = await session.execute(stmt)
        workspace = result.scalar_one_or_none()
        if workspace is None:
            raise ValidationError(
                message=(
                    "Org has no workspaces. Bootstrap one via "
                    "POST /api/v1/orgs which auto-creates a default."
                ),
            )
        workspace_id = workspace.id

    project_id = new_uuid7()
    # The tenant data schema name is deterministic so the SchemaApplier (D1)
    # can re-derive it from project_id without a second DB lookup.
    schema_name = f"tenant_{project_id.hex[:24]}"

    try:
        session.add(Project(
            id=project_id,
            organization_id=tenant.organization_id,
            workspace_id=workspace_id,
            name=body.name,
            slug=body.slug,
            description=body.description,
            deployment_mode=body.deployment_mode,
            tenant_data_schema_name=schema_name,
            created_by=tenant.user_id,
        ))
        await session.flush()
    except IntegrityError as exc:
        raise BasefloError(
            error_code="BF-VALID-009",
            message=(
                f"Project slug {body.slug!r} already exists in this workspace."
            ),
            status_code=409,
            cause=exc,
        ) from exc

    logger.info(
        "project_created",
        project_id=str(project_id),
        organization_id=str(tenant.organization_id),
        workspace_id=str(workspace_id),
        slug=body.slug,
    )
    return CreateProjectResponse(
        project_id=project_id,
        workspace_id=workspace_id,
        slug=body.slug,
    )


# ---------- GET /projects/{id} ----------


@router.get(
    "/projects/{project_id}",
    response_model=ProjectSummary,
    summary="Fetch one project (RLS-scoped to the active org)",
)
async def get_project(
    project_id: UUID,
    tenant: Annotated[TenantCtx, Depends(require_tenant)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> ProjectSummary:
    project = await session.get(Project, project_id)
    if project is None or project.organization_id != tenant.organization_id:
        raise NotFoundError(
            message=f"Project {project_id} not found.",
            error_code="BF-API-001",
        )
    return ProjectSummary(
        id=project.id,
        organization_id=project.organization_id,
        workspace_id=project.workspace_id,
        name=project.name,
        slug=project.slug,
        description=project.description,
        deployment_mode=project.deployment_mode,
        current_version_id=project.current_version_id,
        tenant_data_schema_name=project.tenant_data_schema_name,
        currency=project.currency,
        created_at=project.created_at,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Web-app (camelCase) surface — used by the SPA at app.baseflo.com.
#
# These endpoints layer on top of the existing CLI surface; they're additions,
# not replacements. The CLI endpoints (POST /orgs, POST /projects, etc.) stay
# exactly as they were so the Go CLI keeps working.
# ─────────────────────────────────────────────────────────────────────────────


class OrgWebPayload(BaseModel):
    """Org row in the shape the SPA's Zod `OrgSchema` expects."""
    id: str
    slug: str
    name: str
    plan: str
    region: str
    status: str
    createdAt: str


class ProjectWebPayload(BaseModel):
    """Project row in the shape the SPA's Zod `ProjectSummarySchema` expects."""
    id: str
    organizationId: str
    slug: str
    name: str
    description: str | None
    deploymentMode: str
    currentVersionId: str | None
    createdAt: str
    updatedAt: str
    status: str
    currency: str
    connectorCount: int = 0
    versionCount: int = 1


def _membership_to_org_web(membership: ResolvedMembership) -> OrgWebPayload:
    created_at = membership.organization_created_at or datetime.now(UTC)
    return OrgWebPayload(
        id=str(membership.organization_id),
        slug=membership.organization_slug,
        name=membership.organization_name,
        plan=membership.plan,
        region=membership.region,
        status=membership.status,
        createdAt=created_at.isoformat(),
    )


def _project_to_web(
    project: Project, *, connector_count: int = 0, version_count: int = 1
) -> ProjectWebPayload:
    status: str
    if project.current_version_id is not None:
        status = "ready"
    else:
        status = "no_connectors"
    return ProjectWebPayload(
        id=str(project.id),
        organizationId=str(project.organization_id),
        slug=project.slug,
        name=project.name,
        description=project.description,
        deploymentMode=project.deployment_mode,
        currentVersionId=str(project.current_version_id)
        if project.current_version_id is not None
        else None,
        createdAt=project.created_at.isoformat(),
        updatedAt=project.updated_at.isoformat() if project.updated_at else project.created_at.isoformat(),
        status=status,
        currency=project.currency,
        connectorCount=connector_count,
        versionCount=version_count,
    )


# ---------- GET /orgs (list memberships → orgs) ----------


@router.get(
    "/orgs",
    response_model=list[OrgWebPayload],
    summary="List organizations the current user belongs to",
)
async def list_orgs(
    user: Annotated[UserHandle, Depends(require_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> list[OrgWebPayload]:
    memberships = await MembershipRepository(session).list_for_user(user.id)
    return [_membership_to_org_web(m) for m in memberships]


async def _get_org_access_by_slug_or_404(
    *, slug: str, user_id: UUID, session: AsyncSession
) -> ResolvedMembership:
    """Verify membership for an org slug, then set RLS scope to that org."""
    memberships = await MembershipRepository(session).list_for_user(user_id)
    for membership in memberships:
        if membership.organization_slug == slug:
            await session.execute(
                text("SELECT set_config('app.organization_id', :org, true)"),
                {"org": str(membership.organization_id)},
            )
            return membership
    raise NotFoundError(
        message=f"Organization {slug!r} not found.",
        error_code="BF-API-001",
    )


@router.get(
    "/orgs/{slug}",
    response_model=OrgWebPayload,
    summary="Get one organization by slug (RLS-scoped to caller's memberships)",
)
async def get_org_by_slug(
    slug: str,
    user: Annotated[UserHandle, Depends(require_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> OrgWebPayload:
    membership = await _get_org_access_by_slug_or_404(
        slug=slug, user_id=user.id, session=session,
    )
    return _membership_to_org_web(membership)


# ---------- GET /orgs/{slug}/projects ----------


@router.get(
    "/orgs/{slug}/projects",
    response_model=list[ProjectWebPayload],
    summary="List projects under an organization (by slug)",
)
async def list_projects_by_org_slug(
    slug: str,
    user: Annotated[UserHandle, Depends(require_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> list[ProjectWebPayload]:
    org = await _get_org_access_by_slug_or_404(
        slug=slug, user_id=user.id, session=session,
    )
    stmt = (
        select(Project)
        .where(Project.organization_id == org.organization_id, Project.deleted_at.is_(None))
        .order_by(Project.created_at.desc())
    )
    rows = (await session.execute(stmt)).scalars().all()
    return [_project_to_web(p) for p in rows]


# ---------- GET /orgs/{slug}/projects/{project_slug} ----------


@router.get(
    "/orgs/{slug}/projects/{project_slug}",
    response_model=ProjectWebPayload,
    summary="Get one project by org slug + project slug",
)
async def get_project_by_slug(
    slug: str,
    project_slug: str,
    user: Annotated[UserHandle, Depends(require_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> ProjectWebPayload:
    org = await _get_org_access_by_slug_or_404(
        slug=slug, user_id=user.id, session=session,
    )
    stmt = (
        select(Project)
        .where(
            Project.organization_id == org.organization_id,
            Project.slug == project_slug,
            Project.deleted_at.is_(None),
        )
        .limit(1)
    )
    project = (await session.execute(stmt)).scalar_one_or_none()
    if project is None:
        raise NotFoundError(
            message=f"Project {project_slug!r} not found in {slug!r}.",
            error_code="BF-API-001",
        )
    return _project_to_web(project)


# ---------- POST /orgs/{slug}/projects (slug-context project create) ----------


@router.post(
    "/orgs/{slug}/projects",
    response_model=ProjectWebPayload,
    status_code=201,
    summary="Create a project under an organization (by slug)",
)
async def create_project_under_org(
    slug: str,
    body: CreateProjectRequest,
    user: Annotated[UserHandle, Depends(require_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> ProjectWebPayload:
    org = await _get_org_access_by_slug_or_404(
        slug=slug, user_id=user.id, session=session,
    )
    if body.deployment_mode not in {dm.value for dm in DeploymentMode}:
        raise ValidationError(
            message=f"Unknown deployment_mode {body.deployment_mode!r}.",
        )

    workspace_id = body.workspace_id
    if workspace_id is None:
        ws_stmt = (
            select(Workspace)
            .where(Workspace.organization_id == org.organization_id, Workspace.deleted_at.is_(None))
            .order_by(Workspace.created_at)
            .limit(1)
        )
        workspace = (await session.execute(ws_stmt)).scalar_one_or_none()
        if workspace is None:
            raise ValidationError(message="Org has no workspaces.")
        workspace_id = workspace.id

    project_id = new_uuid7()
    schema_name = f"tenant_{project_id.hex[:24]}"
    try:
        project = Project(
            id=project_id,
            organization_id=org.organization_id,
            workspace_id=workspace_id,
            name=body.name,
            slug=body.slug,
            description=body.description,
            deployment_mode=body.deployment_mode,
            tenant_data_schema_name=schema_name,
            created_by=user.id,
        )
        session.add(project)
        await session.flush()
    except IntegrityError as exc:
        raise BasefloError(
            error_code="BF-VALID-009",
            message=f"Project slug {body.slug!r} already exists in this workspace.",
            status_code=409,
            cause=exc,
        ) from exc

    return _project_to_web(project)
