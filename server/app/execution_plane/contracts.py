"""Typed contracts for deterministic analysis execution."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class ExecutionPlaneError(Exception):
    code = "EXECUTION_PLANE_ERROR"

    def __init__(self, message: str, *, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details or {}


class PlanValidationError(ExecutionPlaneError):
    code = "PLAN_VALIDATION_ERROR"


class PlanCompileError(ExecutionPlaneError):
    code = "PLAN_COMPILE_ERROR"


class ExecutionRuntimeError(ExecutionPlaneError):
    code = "EXECUTION_RUNTIME_ERROR"


class ExecutionModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ExecutionWarning(ExecutionModel):
    code: str
    message: str
    details: dict[str, Any] = Field(default_factory=dict)


class ResolvedAsset(ExecutionModel):
    asset_id: str
    qualified_name: str
    storage_table: str
    label: str
    row_count: int


class ResolvedField(ExecutionModel):
    field_id: str
    asset_id: str
    name: str
    observed_type: str
    storage_type: str
    profile: dict[str, Any] = Field(default_factory=dict)


class ResolvedRelationship(ExecutionModel):
    left_field_id: str
    right_field_id: str
    confidence: float = Field(ge=0.0, le=1.0)
    evidence: dict[str, Any] = Field(default_factory=dict)


class ExecutionCatalog(ExecutionModel):
    assets: dict[str, ResolvedAsset]
    fields: dict[str, ResolvedField]
    relationships: list[ResolvedRelationship] = Field(default_factory=list)

    def asset_for_field(self, field_id: str) -> ResolvedAsset:
        field = self.fields[field_id]
        return self.assets[field.asset_id]

    def relationship_allowed(self, left_field_id: str, right_field_id: str) -> bool:
        left = self.fields[left_field_id]
        right = self.fields[right_field_id]
        if left.asset_id == right.asset_id:
            return True
        for rel in self.relationships:
            if {rel.left_field_id, rel.right_field_id} == {left_field_id, right_field_id}:
                return True
        return False


class NormalizedExecutionNode(ExecutionModel):
    id: str
    op: str
    inputs: list[str] = Field(default_factory=list)
    asset_ids: list[str] = Field(default_factory=list)
    field_ids: list[str] = Field(default_factory=list)


class NormalizedExecutionPlan(ExecutionModel):
    graph_id: str
    hypothesis_id: str
    output: str
    nodes: list[NormalizedExecutionNode]
    source_asset_ids: list[str]
    field_ids: list[str]
    allowed_storage_tables: list[str]

    @property
    def operation_count(self) -> int:
        return len(self.nodes)


@dataclass(slots=True)
class ColumnState:
    alias: str
    field_id: str | None = None
    asset_id: str | None = None
    observed_type: str = "unknown"
    source_name: str | None = None

    def lineage(self) -> dict[str, Any]:
        payload: dict[str, Any] = {"alias": self.alias}
        if self.field_id:
            payload["field_id"] = self.field_id
        if self.asset_id:
            payload["asset_id"] = self.asset_id
        if self.source_name:
            payload["source_name"] = self.source_name
        if self.observed_type:
            payload["observed_type"] = self.observed_type
        return payload


@dataclass(slots=True)
class NodeState:
    sql: str
    columns: dict[str, ColumnState] = field(default_factory=dict)
    fields: dict[str, ColumnState] = field(default_factory=dict)
    kind: Literal["relation"] = "relation"

    def lineage(self) -> list[dict[str, Any]]:
        return [column.lineage() for column in self.columns.values()]


class CompiledAnalysisPlan(ExecutionModel):
    graph_id: str
    sql: str
    output_node: str
    source_asset_ids: list[str] = Field(default_factory=list)
    source_tables: list[str] = Field(default_factory=list)
    field_ids: list[str] = Field(default_factory=list)
    operation_count: int = 0
    lineage: list[dict[str, Any]] = Field(default_factory=list)
    warnings: list[ExecutionWarning] = Field(default_factory=list)
