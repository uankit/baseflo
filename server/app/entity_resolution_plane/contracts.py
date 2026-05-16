"""Contracts for Splink-backed entity resolution."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class EntityResolutionModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


EntityResolutionFieldRole = Literal["name", "email", "phone", "identifier", "address", "category", "unknown"]


class EntityResolutionField(EntityResolutionModel):
    field_id: str
    asset_id: str
    label: str
    role: EntityResolutionFieldRole
    weight: float = Field(default=1.0, ge=0.0, le=1.0)


class EntityResolutionDataset(EntityResolutionModel):
    dataset_id: str
    label: str
    rows: list[dict[str, Any]]
    field_map: dict[str, str]


class EntityResolutionPlan(EntityResolutionModel):
    plan_id: str
    surface_id: str
    view_id: str
    entity: str
    link_type: Literal["dedupe_only", "link_only", "link_and_dedupe"]
    fields: list[EntityResolutionField]
    blocking_fields: list[str] = Field(default_factory=list)
    threshold_match_probability: float = Field(default=0.85, ge=0.0, le=1.0)
    why: str
    engine: Literal["splink"] = "splink"


class EntityMatch(EntityResolutionModel):
    left_dataset_id: str | None = None
    left_record_id: str
    right_dataset_id: str | None = None
    right_record_id: str
    match_probability: float = Field(ge=0.0, le=1.0)
    match_weight: float | None = None
    evidence: dict[str, Any] = Field(default_factory=dict)


class EntityCluster(EntityResolutionModel):
    cluster_id: str
    record_refs: list[str]
    confidence: float = Field(ge=0.0, le=1.0)


class EntityResolutionExecution(EntityResolutionModel):
    plan_id: str
    status: Literal["planned", "completed", "failed"]
    matches: list[EntityMatch] = Field(default_factory=list)
    clusters: list[EntityCluster] = Field(default_factory=list)
    row_count: int = 0
    error: str | None = None
    engine: Literal["splink"] = "splink"


class EntityResolutionRunResult(EntityResolutionModel):
    plans: list[EntityResolutionPlan] = Field(default_factory=list)
    executions: list[EntityResolutionExecution] = Field(default_factory=list)
    generated_from: dict[str, Any] = Field(default_factory=dict)
