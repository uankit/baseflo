"""Repository layer.

Per docs/05-coding-rules.md §3.2, services never construct SQL or use Sessions
directly; repositories are the only path. Every multi-tenant repository
receives a `TenantCtx` and relies on RLS + explicit org filtering.
"""

from __future__ import annotations

from app.repositories.agent_feed import AgentFeedRepository
from app.repositories.agent_tasks import AgentTaskRepository
from app.repositories.analytics_events import AnalyticsEventRepository
from app.repositories.conversations import (
    ConversationEventRepository,
    ConversationMessageRepository,
    ConversationRepository,
)
from app.repositories.jobs import GenerationJobRepository
from app.repositories.projects import ProjectRepository, WorkspaceRepository
from app.repositories.workspace_builds import WorkspaceBuildRepository

__all__ = [
    "AgentFeedRepository",
    "AgentTaskRepository",
    "AnalyticsEventRepository",
    "ConversationEventRepository",
    "ConversationMessageRepository",
    "ConversationRepository",
    "GenerationJobRepository",
    "ProjectRepository",
    "WorkspaceBuildRepository",
    "WorkspaceRepository",
]
