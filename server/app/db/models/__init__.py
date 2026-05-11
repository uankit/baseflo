"""SQLAlchemy ORM models.

Importing this package registers every model with the declarative metadata.
Migrations and tests should `from app.db import models  # noqa: F401` so all
tables are present on `Base.metadata`.
"""

from __future__ import annotations

from app.db.models.agent_feed import AgentFeedEntry
from app.db.models.agent_task import AgentTask, AgentTaskKind, AgentTaskStatus
from app.db.models.analytics_event import AnalyticsEvent, EventSource
from app.db.models.api_key import ApiKey
from app.db.models.audit import ActorType, AuditAction, AuditEvent
from app.db.models.billing import BillingProvider, BillingSubscription
from app.db.models.connector import Connector, ConnectorStatus, ConnectorToken, TokenType
from app.db.models.conversation import (
    Conversation,
    ConversationEvent,
    ConversationMessage,
    ConversationState,
    EventType,
    MessageAuthor,
)
from app.db.models.entity_id_map import EntityIdMap
from app.db.models.entity_identity_index import EntityIdentityIndex
from app.db.models.generation import (
    AgentRun,
    AgentRunAttempt,
    AgentRunFinalStatus,
    GenerationJob,
    GenerationStep,
    JobKind,
    JobStatus,
    StepStatus,
)
from app.db.models.magic_link_token import MagicLinkToken
from app.db.models.membership import Membership, Role
from app.db.models.oauth_identity import OAuthIdentity, OAuthProvider
from app.db.models.organization import Organization, OrganizationPlan, OrganizationStatus
from app.db.models.project import (
    DeploymentMode,
    Project,
    ProjectVersion,
    ValidationStatus,
)
from app.db.models.refinement import Refinement, RefinementStatus
from app.db.models.session_record import SessionRecord
from app.db.models.sharing import (
    Export,
    ExportFormat,
    ExportStatus,
    FeedbackEvent,
    FeedbackTargetType,
    ShareLink,
)
from app.db.models.tenant_data_application import (
    TenantDataApplication,
    TenantDataApplicationKind,
    TenantDataApplicationStatus,
)
from app.db.models.user import User
from app.db.models.workspace import Workspace
from app.db.models.workspace_build import (
    WorkspaceBuild,
    WorkspaceBuildSnapshot,
    WorkspaceBuildSnapshotStatus,
    WorkspaceBuildStatus,
)
from app.artifacts.types import ArtifactRecord

__all__ = [
    "ActorType",
    "AgentFeedEntry",
    "AgentRun",
    "AgentRunAttempt",
    "AgentRunFinalStatus",
    "AgentTask",
    "AgentTaskKind",
    "AgentTaskStatus",
    "AnalyticsEvent",
    "ApiKey",
    "AuditAction",
    "AuditEvent",
    "BillingProvider",
    "BillingSubscription",
    "Connector",
    "ConnectorStatus",
    "ConnectorToken",
    "Conversation",
    "ConversationEvent",
    "ConversationMessage",
    "ConversationState",
    "DeploymentMode",
    "EntityIdMap",
    "EntityIdentityIndex",
    "EventSource",
    "EventType",
    "Export",
    "ExportFormat",
    "ExportStatus",
    "FeedbackEvent",
    "FeedbackTargetType",
    "GenerationJob",
    "GenerationStep",
    "JobKind",
    "JobStatus",
    "MagicLinkToken",
    "Membership",
    "MessageAuthor",
    "OAuthIdentity",
    "OAuthProvider",
    "Organization",
    "OrganizationPlan",
    "OrganizationStatus",
    "Project",
    "ProjectVersion",
    "Refinement",
    "RefinementStatus",
    "Role",
    "SessionRecord",
    "ShareLink",
    "StepStatus",
    "TenantDataApplication",
    "TenantDataApplicationKind",
    "TenantDataApplicationStatus",
    "TokenType",
    "User",
    "ValidationStatus",
    "Workspace",
    "WorkspaceBuild",
    "WorkspaceBuildSnapshot",
    "WorkspaceBuildSnapshotStatus",
    "WorkspaceBuildStatus",
]
