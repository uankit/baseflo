"""Workspace + Project repositories."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import NotFoundError
from app.db.models.project import Project, ProjectVersion
from app.db.models.workspace import Workspace


class WorkspaceRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, workspace_id: UUID) -> Workspace:
        result = await self._session.get(Workspace, workspace_id)
        if result is None or result.deleted_at is not None:
            raise NotFoundError(
                message=f"Workspace {workspace_id} not found.",
                error_code="BF-API-001",
                details={"workspace_id": str(workspace_id)},
            )
        return result

    async def create(self, workspace: Workspace) -> Workspace:
        self._session.add(workspace)
        await self._session.flush()
        return workspace


class ProjectRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, project_id: UUID) -> Project:
        result = await self._session.get(Project, project_id)
        if result is None or result.deleted_at is not None:
            raise NotFoundError(
                message=f"Project {project_id} not found.",
                error_code="BF-API-001",
                details={"project_id": str(project_id)},
            )
        return result

    async def create(self, project: Project) -> Project:
        self._session.add(project)
        await self._session.flush()
        return project

    async def list_for_workspace(self, workspace_id: UUID) -> list[Project]:
        stmt = (
            select(Project)
            .where(Project.workspace_id == workspace_id)
            .where(Project.deleted_at.is_(None))
            .order_by(Project.created_at.desc())
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def get_current_version(self, project_id: UUID) -> ProjectVersion | None:
        """Return the project's current version row, or None if none yet.

        Falls back to the highest version_number if `current_version_id` is
        unset (e.g., a project that's been created but not yet generated).
        """
        project = await self.get(project_id)
        if project.current_version_id is not None:
            version = await self._session.get(
                ProjectVersion, project.current_version_id
            )
            if version is not None:
                return version
        stmt = (
            select(ProjectVersion)
            .where(ProjectVersion.project_id == project_id)
            .order_by(ProjectVersion.version_number.desc())
            .limit(1)
        )
        return (await self._session.execute(stmt)).scalar_one_or_none()
