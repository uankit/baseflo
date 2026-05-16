"""OpenLineage-compatible lineage contracts for Baseflo."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class LineageModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class LineageDataset(LineageModel):
    namespace: str = "baseflo"
    name: str
    facets: dict[str, Any] = Field(default_factory=dict)


class LineageField(LineageModel):
    field_id: str
    asset_id: str | None = None
    name: str | None = None
    role: str | None = None
    facets: dict[str, Any] = Field(default_factory=dict)


class LineageColumnMapping(LineageModel):
    output_field: str
    input_fields: list[str] = Field(default_factory=list)
    transformation: str


class LineageJob(LineageModel):
    namespace: str = "baseflo"
    name: str
    facets: dict[str, Any] = Field(default_factory=dict)


class LineageRun(LineageModel):
    run_id: str
    event_type: Literal["START", "COMPLETE", "FAIL"] = "COMPLETE"
    event_time: datetime = Field(default_factory=lambda: datetime.now(UTC))
    job: LineageJob
    inputs: list[LineageDataset] = Field(default_factory=list)
    outputs: list[LineageDataset] = Field(default_factory=list)
    fields: list[LineageField] = Field(default_factory=list)
    column_lineage: list[LineageColumnMapping] = Field(default_factory=list)
    facets: dict[str, Any] = Field(default_factory=dict)


class LineagePackage(LineageModel):
    runs: list[LineageRun] = Field(default_factory=list)
    datasets: list[LineageDataset] = Field(default_factory=list)
    generated_from: dict[str, Any] = Field(default_factory=dict)
