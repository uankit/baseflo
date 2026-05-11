"""Agent orchestrator service — task queue + feed management.

Thin service layer over AgentTaskRepository and AgentFeedRepository.
Does not execute agent logic; only manages queue state and feed entries.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from app.db.models.agent_feed import AgentFeedEntry
from app.db.models.agent_task import AgentTask, AgentTaskKind, AgentTaskStatus
from app.repositories.agent_feed import AgentFeedRepository
from app.repositories.agent_tasks import AgentTaskRepository


class AgentOrchestrator:
    def __init__(
        self,
        task_repo: AgentTaskRepository,
        feed_repo: AgentFeedRepository,
    ) -> None:
        self._task_repo = task_repo
        self._feed_repo = feed_repo

    async def enqueue_task(
        self,
        project_id: UUID,
        agent_id: str,
        kind: AgentTaskKind,
        payload: dict[str, Any] | None = None,
        *,
        priority: int = 0,
    ) -> AgentTask:
        """Create a pending task row."""
        task = AgentTask(
            project_id=project_id,
            agent_id=agent_id,
            kind=kind.value,
            status=AgentTaskStatus.PENDING.value,
            priority=priority,
            payload=payload or {},
        )
        return await self._task_repo.create(task)

    async def get_agent_status(
        self,
        project_id: UUID,
        agent_id: str,
    ) -> dict[str, Any]:
        """Return agent status, last activity, and pending task count."""
        pending = await self._task_repo.list_for_project(
            project_id, status=AgentTaskStatus.PENDING, agent_id=agent_id, limit=1000
        )
        running = await self._task_repo.list_for_project(
            project_id, status=AgentTaskStatus.RUNNING, agent_id=agent_id, limit=1000
        )
        recent_feed = await self._feed_repo.list_for_project(
            project_id, agent_id=agent_id, limit=1
        )
        last_activity = recent_feed[0].created_at if recent_feed else None
        return {
            "agent_id": agent_id,
            "pending_count": len(pending),
            "running_count": len(running),
            "last_activity_at": last_activity.isoformat() if last_activity else None,
        }

    async def generate_feed_entry(
        self,
        project_id: UUID,
        agent_id: str,
        entry_type: str,
        content: str,
        context: dict[str, Any] | None = None,
    ) -> AgentFeedEntry:
        """Log an agent thought / observation / action to the feed."""
        entry = AgentFeedEntry(
            project_id=project_id,
            agent_id=agent_id,
            entry_type=entry_type,
            content=content,
            context=context or {},
        )
        return await self._feed_repo.create(entry)

    async def get_feed(
        self,
        project_id: UUID,
        *,
        agent_id: str | None = None,
        limit: int = 50,
    ) -> list[AgentFeedEntry]:
        """Return feed entries for a project, optionally filtered by agent."""
        return await self._feed_repo.list_for_project(
            project_id, agent_id=agent_id, limit=limit
        )
