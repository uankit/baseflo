"""Agent API routes — read-only feed and task queue visibility.

These endpoints let users SEE what agents are doing (feed entries, task status)
but never MUTATE the queue. Tasks are created internally by the build pipeline
and future recurring-job runner.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import require_tenant
from app.core.context import TenantCtx
from app.core.errors import NotFoundError
from app.db.models.agent_task import AgentTaskStatus
from app.db.models.project import Project
from app.db.session import open_session
from app.repositories.agent_feed import AgentFeedRepository
from app.repositories.agent_tasks import AgentTaskRepository
from app.services.agent_orchestrator import AgentOrchestrator

router = APIRouter(prefix="/projects", tags=["agents"])

# ── Baseflo's built-in agents (internal constant; not user-extensible) ──────

_BUILDFLO_AGENTS: list[dict[str, Any]] = [
    {
        "id": "source",
        "name": "Source",
        "role": "Data Engineer",
        "personality": "Maps raw inputs into structured streams",
        "artifact_type": "source_map",
        "tone": "accent",
        "icon": "Database",
    },
    {
        "id": "reconciliation",
        "name": "Recon",
        "role": "Data Steward",
        "personality": "Resolves conflicts and unifies entities",
        "artifact_type": "entity_graph",
        "tone": "purple",
        "icon": "ShieldCheck",
    },
    {
        "id": "schema",
        "name": "Schema",
        "role": "Architect",
        "personality": "Designs the unified model blueprint",
        "artifact_type": "schema_ir",
        "tone": "emerald",
        "icon": "Zap",
    },
    {
        "id": "insight",
        "name": "Insight",
        "role": "Analyst",
        "personality": "Surfaces patterns and anomalies",
        "artifact_type": "insight_board",
        "tone": "amber",
        "icon": "Lightbulb",
    },
]


async def get_db_session() -> AsyncIterator[AsyncSession]:
    async with open_session() as session:
        yield session


class AgentStatusResponse(BaseModel):
    agent_id: str
    name: str
    role: str
    personality: str
    artifact_type: str
    tone: str
    icon: str
    pending_count: int
    running_count: int
    last_activity_at: str | None


class FeedEntryResponse(BaseModel):
    id: str
    projectId: str
    agentId: str
    entryType: str
    content: str
    context: dict[str, Any]
    createdAt: str
    acknowledgedAt: str | None


class TaskResponse(BaseModel):
    id: str
    projectId: str
    agentId: str
    kind: str
    status: str
    priority: int
    payload: dict[str, Any]
    result: dict[str, Any] | None
    error: dict[str, Any] | None
    createdAt: str
    startedAt: str | None
    completedAt: str | None


@router.get("/{project_id}/agents")
async def list_project_agents(
    project_id: UUID,
    tenant: TenantCtx = Depends(require_tenant),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """List Baseflo's built-in agents with their current status for a project."""
    project = await session.get(Project, project_id)
    if project is None or project.organization_id != tenant.organization_id:
        raise NotFoundError(message="Project not found.")

    task_repo = AgentTaskRepository(session)
    feed_repo = AgentFeedRepository(session)
    orchestrator = AgentOrchestrator(task_repo, feed_repo)

    results: list[AgentStatusResponse] = []
    for agent in _BUILDFLO_AGENTS:
        status = await orchestrator.get_agent_status(project_id, agent["id"])
        results.append(
            AgentStatusResponse(
                agent_id=agent["id"],
                name=agent["name"],
                role=agent["role"],
                personality=agent["personality"],
                artifact_type=agent["artifact_type"],
                tone=agent["tone"],
                icon=agent["icon"],
                pending_count=status["pending_count"],
                running_count=status["running_count"],
                last_activity_at=status["last_activity_at"],
            )
        )
    return {"agents": results}


@router.get("/{project_id}/agents/feed")
async def get_agent_feed(
    project_id: UUID,
    agent_id: str | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    tenant: TenantCtx = Depends(require_tenant),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """Get agent feed entries for a project."""
    project = await session.get(Project, project_id)
    if project is None or project.organization_id != tenant.organization_id:
        raise NotFoundError(message="Project not found.")

    feed_repo = AgentFeedRepository(session)
    entries = await feed_repo.list_for_project(project_id, agent_id=agent_id, limit=limit)
    return {
        "entries": [
            FeedEntryResponse(
                id=str(e.id),
                projectId=str(project_id),
                agentId=e.agent_id,
                entryType=e.entry_type,
                content=e.content,
                context=e.context,
                createdAt=e.created_at.isoformat(),
                acknowledgedAt=e.acknowledged_at.isoformat() if e.acknowledged_at else None,
            )
            for e in entries
        ],
    }


@router.get("/{project_id}/agents/tasks")
async def list_agent_tasks(
    project_id: UUID,
    status: AgentTaskStatus | None = Query(None),
    agent_id: str | None = Query(None),
    limit: int = Query(100, ge=1, le=500),
    tenant: TenantCtx = Depends(require_tenant),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """List agent tasks for a project."""
    project = await session.get(Project, project_id)
    if project is None or project.organization_id != tenant.organization_id:
        raise NotFoundError(message="Project not found.")

    task_repo = AgentTaskRepository(session)
    tasks = await task_repo.list_for_project(
        project_id, status=status, agent_id=agent_id, limit=limit
    )
    return {
        "tasks": [
            TaskResponse(
                id=str(t.id),
                projectId=str(t.project_id),
                agentId=t.agent_id,
                kind=t.kind,
                status=t.status,
                priority=t.priority,
                payload=t.payload,
                result=t.result,
                error=t.error,
                createdAt=t.created_at.isoformat(),
                startedAt=t.started_at.isoformat() if t.started_at else None,
                completedAt=t.completed_at.isoformat() if t.completed_at else None,
            )
            for t in tasks
        ],
    }
