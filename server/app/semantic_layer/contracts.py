"""Contracts for Baseflo's governed semantic layer."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class SemanticLayerModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


SemanticObjectKind = Literal["entity", "dimension", "measure", "metric", "surface"]
SemanticAggregateKind = Literal["sum", "avg", "count", "min", "max"]


class SemanticEntity(SemanticLayerModel):
    entity_id: str
    name: str
    plural: str
    description: str
    primary_asset_id: str | None = None
    source_asset_ids: list[str] = Field(default_factory=list)
    field_refs: list[str] = Field(default_factory=list)
    why: str
    confidence: float = Field(ge=0.0, le=1.0)


class SemanticDimension(SemanticLayerModel):
    dimension_id: str
    name: str
    label: str
    kind: str
    entity_id: str | None = None
    field_id: str
    asset_id: str
    data_type: str | None = None
    why: str
    confidence: float = Field(ge=0.0, le=1.0)


class SemanticMeasure(SemanticLayerModel):
    measure_id: str
    name: str
    label: str
    kind: str
    field_id: str
    asset_id: str
    default_aggregate: SemanticAggregateKind
    unit: str | None = None
    why: str
    confidence: float = Field(ge=0.0, le=1.0)


class SemanticMetric(SemanticLayerModel):
    metric_id: str
    name: str
    label: str
    description: str
    measure_refs: list[str] = Field(default_factory=list)
    dimension_refs: list[str] = Field(default_factory=list)
    expression: dict[str, Any] = Field(default_factory=dict)
    default_grain: str | None = None
    source_surface_ids: list[str] = Field(default_factory=list)
    why: str
    confidence: float = Field(ge=0.0, le=1.0)


class SemanticSurfaceBinding(SemanticLayerModel):
    surface_id: str
    title: str
    entity_refs: list[str] = Field(default_factory=list)
    dimension_refs: list[str] = Field(default_factory=list)
    measure_refs: list[str] = Field(default_factory=list)
    metric_refs: list[str] = Field(default_factory=list)
    why: str


class SemanticLayerPackage(SemanticLayerModel):
    entities: list[SemanticEntity] = Field(default_factory=list)
    dimensions: list[SemanticDimension] = Field(default_factory=list)
    measures: list[SemanticMeasure] = Field(default_factory=list)
    metrics: list[SemanticMetric] = Field(default_factory=list)
    surfaces: list[SemanticSurfaceBinding] = Field(default_factory=list)
    generated_from: dict[str, Any] = Field(default_factory=dict)
    confidence: float = Field(ge=0.0, le=1.0)
