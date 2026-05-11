"""Repositories for workspace build graph persistence."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import func, select

from app.core.errors import NotFoundError
from app.core.ids import new_uuid7
from app.db.models.workspace_build import (
    WorkspaceBuild,
    WorkspaceBuildSnapshot,
    WorkspaceBuildSnapshotStatus,
    WorkspaceBuildStatus,
)

if TYPE_CHECKING:
    from uuid import UUID

    from sqlalchemy.ext.asyncio import AsyncSession


class WorkspaceBuildRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self,
        *,
        organization_id: UUID,
        project_id: UUID,
        job_id: UUID,
        conversation_id: UUID | None,
        graph_name: str,
    ) -> WorkspaceBuild:
        existing = await self.get_by_job(job_id)
        if existing is not None:
            return existing

        build = WorkspaceBuild(
            id=new_uuid7(),
            organization_id=organization_id,
            project_id=project_id,
            job_id=job_id,
            conversation_id=conversation_id,
            graph_name=graph_name,
            status=WorkspaceBuildStatus.RUNNING.value,
        )
        self._session.add(build)
        await self._session.flush()
        return build

    async def get(self, build_id: UUID) -> WorkspaceBuild:
        build = await self._session.get(WorkspaceBuild, build_id)
        if build is None:
            raise NotFoundError(
                message=f"Workspace build {build_id} not found.",
                error_code="BF-GRAPH-001",
                details={"build_id": str(build_id)},
            )
        return build

    async def get_by_job(self, job_id: UUID) -> WorkspaceBuild | None:
        stmt = select(WorkspaceBuild).where(WorkspaceBuild.job_id == job_id)
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def get_by_conversation(self, conversation_id: UUID) -> WorkspaceBuild | None:
        stmt = (
            select(WorkspaceBuild)
            .where(WorkspaceBuild.conversation_id == conversation_id)
            .order_by(WorkspaceBuild.created_at.desc())
            .limit(1)
        )
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def get_snapshot(
        self, *, build_id: UUID, snapshot_id: str,
    ) -> WorkspaceBuildSnapshot | None:
        stmt = select(WorkspaceBuildSnapshot).where(
            WorkspaceBuildSnapshot.build_id == build_id,
            WorkspaceBuildSnapshot.snapshot_id == snapshot_id,
        )
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def append_snapshot(
        self,
        *,
        build_id: UUID,
        snapshot_id: str,
        kind: str,
        node_name: str,
        status: str,
        payload: dict[str, Any],
    ) -> WorkspaceBuildSnapshot:
        max_ordinal = (
            await self._session.execute(
                select(func.coalesce(func.max(WorkspaceBuildSnapshot.ordinal), 0)).where(
                    WorkspaceBuildSnapshot.build_id == build_id
                )
            )
        ).scalar_one()
        snapshot = WorkspaceBuildSnapshot(
            id=new_uuid7(),
            build_id=build_id,
            ordinal=int(max_ordinal) + 1,
            snapshot_id=snapshot_id,
            kind=kind,
            node_name=node_name,
            status=status,
            payload=payload,
        )
        self._session.add(snapshot)
        build = await self.get(build_id)
        build.current_node = node_name
        await self._session.flush()
        return snapshot

    async def load_next_created(self, *, build_id: UUID) -> WorkspaceBuildSnapshot | None:
        stmt = (
            select(WorkspaceBuildSnapshot)
            .where(
                WorkspaceBuildSnapshot.build_id == build_id,
                WorkspaceBuildSnapshot.status == WorkspaceBuildSnapshotStatus.CREATED.value,
            )
            .order_by(WorkspaceBuildSnapshot.ordinal.asc())
            .limit(1)
        )
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def update_snapshot_status(
        self,
        *,
        build_id: UUID,
        snapshot_id: str,
        status: WorkspaceBuildSnapshotStatus,
        error: dict[str, Any] | None = None,
        duration_ms: int | None = None,
    ) -> WorkspaceBuildSnapshot:
        snapshot = await self.get_snapshot(build_id=build_id, snapshot_id=snapshot_id)
        if snapshot is None:
            raise NotFoundError(
                message=f"Workspace build snapshot {snapshot_id!r} not found.",
                error_code="BF-GRAPH-002",
                details={"build_id": str(build_id), "snapshot_id": snapshot_id},
            )
        snapshot.status = status.value
        payload = dict(snapshot.payload)
        payload["status"] = status.value
        if status == WorkspaceBuildSnapshotStatus.RUNNING:
            snapshot.started_at = datetime.now(UTC)
            payload["start_ts"] = snapshot.started_at.isoformat()
        if error is not None:
            snapshot.error = error
        if duration_ms is not None:
            snapshot.duration_ms = duration_ms
            payload["duration"] = duration_ms / 1000
        snapshot.payload = payload
        await self._session.flush()
        return snapshot

    async def mark_succeeded(
        self,
        *,
        build_id: UUID,
        result: dict[str, Any],
        project_version_id: UUID | None,
        repair_cycle: int,
    ) -> WorkspaceBuild:
        build = await self.get(build_id)
        build.status = WorkspaceBuildStatus.SUCCEEDED.value
        build.final_result = result
        build.project_version_id = project_version_id
        build.repair_cycle = repair_cycle
        build.completed_at = datetime.now(UTC)
        await self._session.flush()
        return build

    async def mark_failed(
        self,
        *,
        build_id: UUID,
        error: dict[str, Any],
        repair_cycle: int,
    ) -> WorkspaceBuild:
        build = await self.get(build_id)
        build.status = WorkspaceBuildStatus.FAILED.value
        build.error = error
        build.repair_cycle = repair_cycle
        build.completed_at = datetime.now(UTC)
        await self._session.flush()
        return build

    async def mark_cancelled(
        self,
        *,
        build_id: UUID,
        error: dict[str, Any] | None = None,
        repair_cycle: int = 0,
    ) -> WorkspaceBuild:
        build = await self.get(build_id)
        build.status = WorkspaceBuildStatus.CANCELLED.value
        build.error = error or {
            "error_code": "BF-JOB-003",
            "message": "Build cancelled.",
        }
        build.repair_cycle = repair_cycle
        build.completed_at = datetime.now(UTC)
        await self._session.flush()
        return build
