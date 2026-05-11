"""AgentTask repository — CRUD + queue operations."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import NotFoundError
from app.db.models.agent_task import AgentTask, AgentTaskStatus


class AgentTaskRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, task_id: UUID) -> AgentTask:
        result = await self._session.get(AgentTask, task_id)
        if result is None:
            raise NotFoundError(
                message=f"Task {task_id} not found.",
                error_code="BF-API-001",
                details={"task_id": str(task_id)},
            )
        return result

    async def create(self, task: AgentTask) -> AgentTask:
        self._session.add(task)
        await self._session.flush()
        return task

    async def list_for_project(
        self,
        project_id: UUID,
        *,
        status: AgentTaskStatus | None = None,
        agent_id: str | None = None,
        limit: int = 100,
    ) -> list[AgentTask]:
        stmt = (
            select(AgentTask)
            .where(AgentTask.project_id == project_id)
            .order_by(AgentTask.priority.desc(), AgentTask.created_at.asc())
            .limit(limit)
        )
        if status is not None:
            stmt = stmt.where(AgentTask.status == status.value)
        if agent_id is not None:
            stmt = stmt.where(AgentTask.agent_id == agent_id)
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def update_status(
        self,
        task_id: UUID,
        *,
        status: AgentTaskStatus,
        result: dict[str, Any] | None = None,
        error: dict[str, Any] | None = None,
    ) -> AgentTask:
        task = await self.get(task_id)
        task.status = status.value
        if result is not None:
            task.result = result
        if error is not None:
            task.error = error
        await self._session.flush()
        return task

    async def cancel(self, task_id: UUID) -> AgentTask:
        return await self.update_status(
            task_id,
            status=AgentTaskStatus.CANCELLED,
            error={"error_code": "BF-AGENT-003", "message": "Task cancelled by user."},
        )
