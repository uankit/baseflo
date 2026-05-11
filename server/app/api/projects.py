"""Project routes."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select

from app.auth.dependencies import require_auth
from app.core.context import TenantCtx
from app.core.errors import BasefloError
from app.db.models import Project
from app.db.session import open_session

router = APIRouter()


class ProjectCreateRequest(BaseModel):
    name: str


class ProjectResponse(BaseModel):
    id: str
    organization_id: str
    name: str
    slug: str
    created_at: str


@router.get("")
async def list_projects(
    tenant: Annotated[TenantCtx, Depends(require_auth)],
) -> list[ProjectResponse]:
    """List all projects for the current organization."""
    async with open_session() as session:
        result = await session.execute(
            select(Project).where(Project.organization_id == tenant.org_id)
        )
        projects = result.scalars().all()

    return [
        ProjectResponse(
            id=str(p.id),
            organization_id=str(p.organization_id),
            name=p.name,
            slug=p.slug,
            created_at=p.created_at.isoformat() if p.created_at else "",
        )
        for p in projects
    ]


@router.post("")
async def create_project(
    body: ProjectCreateRequest,
    tenant: Annotated[TenantCtx, Depends(require_auth)],
) -> ProjectResponse:
    """Create a new project."""
    from uuid import uuid4

    slug = body.name.lower().replace(" ", "-")[:50] + "-" + str(uuid4())[:8]
    async with open_session() as session:
        project = Project(
            organization_id=tenant.org_id,
            name=body.name,
            slug=slug,
        )
        session.add(project)
        await session.flush()

        return ProjectResponse(
            id=str(project.id),
            organization_id=str(project.organization_id),
            name=project.name,
            slug=project.slug,
            created_at=project.created_at.isoformat() if project.created_at else "",
        )


@router.get("/{project_id}")
async def get_project(
    project_id: UUID,
    tenant: Annotated[TenantCtx, Depends(require_auth)],
) -> ProjectResponse:
    """Get a project by ID."""
    async with open_session() as session:
        project = await session.get(Project, project_id)
        if project is None:
            raise BasefloError(
                message="Project not found",
                error_code="BF-PROJ-001",
                status_code=404,
            )
        if project.organization_id != tenant.org_id:
            raise BasefloError(
                message="Unauthorized",
                error_code="BF-PROJ-002",
                status_code=403,
            )

    return ProjectResponse(
        id=str(project.id),
        organization_id=str(project.organization_id),
        name=project.name,
        slug=project.slug,
        created_at=project.created_at.isoformat() if project.created_at else "",
    )
