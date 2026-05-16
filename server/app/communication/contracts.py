"""Standard communication contracts for Baseflo async runs and live events."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Literal, Protocol
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field

RunKind = Literal["operating", "source_sync", "action", "export"]
RunStatus = Literal["queued", "running", "completed", "partial", "failed", "cancelled"]


class CommunicationModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class RunEvent(CommunicationModel):
    event_id: UUID = Field(default_factory=uuid4)
    run_id: UUID
    organization_id: UUID
    type: str
    stage: str
    message: str
    progress: float | None = Field(default=None, ge=0, le=1)
    payload: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class RunRecord(CommunicationModel):
    run_id: UUID
    organization_id: UUID
    kind: RunKind
    status: RunStatus = "queued"
    request: dict[str, Any] = Field(default_factory=dict)
    result: dict[str, Any] | None = None
    error: dict[str, Any] | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    started_at: datetime | None = None
    completed_at: datetime | None = None


class RunAccepted(CommunicationModel):
    run_id: UUID
    kind: RunKind
    status: RunStatus
    result_url: str
    events_url: str


class RunState(CommunicationModel):
    run: RunRecord
    events: list[RunEvent] = Field(default_factory=list)


class RunEventPublisher(Protocol):
    async def __call__(
        self,
        *,
        type: str,
        stage: str,
        message: str,
        progress: float | None = None,
        payload: dict[str, Any] | None = None,
    ) -> None: ...
