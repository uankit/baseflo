"""Contracts for generated Business View / Operating Room packages."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

BusinessViewSectionKind = Literal[
    "sales",
    "receivables",
    "inventory",
    "customers_parties",
    "products_items",
    "expenses",
    "profit_loss",
    "operations",
    "data_quality",
    "connected_data",
]


class BusinessViewModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class BusinessViewMetric(BusinessViewModel):
    label: str
    value: str
    unit: str | None = None
    why: str
    evidence_refs: list[str] = Field(default_factory=list)


class BusinessViewDrilldown(BusinessViewModel):
    drilldown_id: str
    label: str
    entity: str | None = None
    question: str
    graph_refs: list[str] = Field(default_factory=list)
    field_refs: list[str] = Field(default_factory=list)
    artifact_refs: list[str] = Field(default_factory=list)


class BusinessViewSection(BusinessViewModel):
    section_id: str
    kind: BusinessViewSectionKind
    title: str
    description: str
    why_built: str
    confidence: float = Field(ge=0.0, le=1.0)
    tags: list[str] = Field(default_factory=list)
    metrics: list[BusinessViewMetric] = Field(default_factory=list)
    source_asset_ids: list[str] = Field(default_factory=list)
    field_refs: list[str] = Field(default_factory=list)
    graph_refs: list[str] = Field(default_factory=list)
    insight_refs: list[str] = Field(default_factory=list)
    table_refs: list[str] = Field(default_factory=list)
    chart_refs: list[str] = Field(default_factory=list)
    action_refs: list[str] = Field(default_factory=list)
    suggested_questions: list[str] = Field(default_factory=list)
    drilldowns: list[BusinessViewDrilldown] = Field(default_factory=list)


class BusinessEntityView(BusinessViewModel):
    entity: str
    plural: str
    description: str
    why_available: str
    source_asset_ids: list[str] = Field(default_factory=list)
    field_refs: list[str] = Field(default_factory=list)
    graph_refs: list[str] = Field(default_factory=list)
    suggested_questions: list[str] = Field(default_factory=list)


class BusinessViewPackage(BusinessViewModel):
    headline: str
    summary: str
    why: str
    sections: list[BusinessViewSection]
    entity_views: list[BusinessEntityView] = Field(default_factory=list)
    generated_from: dict[str, Any] = Field(default_factory=dict)
    confidence: float = Field(ge=0.0, le=1.0)
