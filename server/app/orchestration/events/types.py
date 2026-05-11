"""Typed event payloads + envelope.

Per docs/40-features/JOBS-AND-SSE.md §3.3, every event_type has a typed
payload. Envelope (`ConversationEventEnvelope`) is what subscribers receive
after the publisher hydrates the DB row.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Annotated, Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field


class EventType(StrEnum):
    CONVERSATION_MESSAGE = "conversation.message"
    CLARIFICATION_REQUIRED = "clarification.required"
    AGENT_START = "agent.start"
    AGENT_COMPLETE = "agent.complete"
    VALIDATION_PASSED = "validation.passed"
    VALIDATION_WARNING = "validation.warning"
    VALIDATION_FAILED = "validation.failed"
    ARTIFACT_READY = "artifact.ready"
    WORKSPACE_READY = "workspace.ready"
    ERROR_RECOVERABLE = "error.recoverable"
    ERROR_TERMINAL = "error.terminal"


# ---------- Per-event payloads ----------


class ConversationMessagePayload(BaseModel):
    type: Literal[EventType.CONVERSATION_MESSAGE] = EventType.CONVERSATION_MESSAGE
    message_id: UUID
    author: str
    content: str


class ClarificationRequiredPayload(BaseModel):
    type: Literal[EventType.CLARIFICATION_REQUIRED] = EventType.CLARIFICATION_REQUIRED
    questions: list[str]


class AgentStartPayload(BaseModel):
    type: Literal[EventType.AGENT_START] = EventType.AGENT_START
    agent_name: str
    stage_index: int
    label: str                          # user-facing copy: "Designing your data model..."


class AgentCompletePayload(BaseModel):
    type: Literal[EventType.AGENT_COMPLETE] = EventType.AGENT_COMPLETE
    agent_name: str
    stage_index: int
    duration_ms: int


class ValidationPayload(BaseModel):
    type: Literal[
        EventType.VALIDATION_PASSED,
        EventType.VALIDATION_WARNING,
        EventType.VALIDATION_FAILED,
    ]
    target: str                         # "schema_ir" | "kpi_definitions" | etc.
    issues: list[str] = []


class ArtifactReadyPayload(BaseModel):
    type: Literal[EventType.ARTIFACT_READY] = EventType.ARTIFACT_READY
    artifact_kind: str
    artifact_id: UUID


class WorkspaceReadyPayload(BaseModel):
    type: Literal[EventType.WORKSPACE_READY] = EventType.WORKSPACE_READY
    project_id: UUID
    project_version_id: UUID


class ErrorPayload(BaseModel):
    type: Literal[EventType.ERROR_RECOVERABLE, EventType.ERROR_TERMINAL]
    error_code: str
    message: str
    details: dict[str, Any] = {}


EventPayload = Annotated[
    ConversationMessagePayload
    | ClarificationRequiredPayload
    | AgentStartPayload
    | AgentCompletePayload
    | ValidationPayload
    | ArtifactReadyPayload
    | WorkspaceReadyPayload
    | ErrorPayload,
    Field(discriminator="type"),
]


# ---------- Envelope ----------


class ConversationEventEnvelope(BaseModel):
    """Hydrated event a subscriber receives.

    `id`/`sequence`/`created_at` come from the DB row; `payload` is the typed
    event-specific body parsed from the persisted JSON.
    """

    id: UUID
    conversation_id: UUID
    sequence: int
    event_type: EventType
    payload: EventPayload
    created_at: datetime
