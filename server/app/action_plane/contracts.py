"""Contracts for Baseflo Action Plane v1."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

ActionType = Literal["email_draft", "export_list", "save_cohort"]
ActionStatus = Literal["proposed", "prepared", "completed", "dismissed"]


class ActionModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ActionRecordDraft(ActionModel):
    artifact_id: UUID
    run_id: UUID | None = None
    action_key: str
    action_type: ActionType
    title: str
    summary: str = ""
    why: str = ""
    source_refs: dict[str, Any] = Field(default_factory=dict)
    payload: dict[str, Any] = Field(default_factory=dict)


class ActionRecord(ActionModel):
    id: UUID
    organization_id: UUID
    artifact_id: UUID | None = None
    run_id: UUID | None = None
    action_key: str
    action_type: ActionType
    status: ActionStatus
    title: str
    summary: str
    why: str
    source_refs: dict[str, Any] = Field(default_factory=dict)
    payload: dict[str, Any] = Field(default_factory=dict)
    prepared_payload: dict[str, Any] = Field(default_factory=dict)
    prepared_at: datetime | None = None
    completed_at: datetime | None = None
    dismissed_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class ActionPlaneRunResult(ActionModel):
    organization_id: UUID
    run_id: UUID
    actions: list[ActionRecord] = Field(default_factory=list)
    created_count: int = 0
    updated_count: int = 0
    skipped_count: int = 0


class ActionList(ActionModel):
    actions: list[ActionRecord] = Field(default_factory=list)


class ActionPrepareRequest(ActionModel):
    options: dict[str, Any] = Field(default_factory=dict)


class SavedCohortRecord(ActionModel):
    id: UUID
    organization_id: UUID
    action_id: UUID | None = None
    cohort_key: str
    name: str
    description: str
    audience: dict[str, Any] = Field(default_factory=dict)
    rows: list[dict[str, Any]] = Field(default_factory=list)
    source_refs: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime


class SavedCohortList(ActionModel):
    cohorts: list[SavedCohortRecord] = Field(default_factory=list)
