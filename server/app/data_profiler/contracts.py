"""Typed evidence contracts emitted by the deterministic data profiler."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class ProfilerModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


ObservedType = Literal[
    "unknown",
    "text",
    "integer",
    "number",
    "money",
    "boolean",
    "date",
    "datetime",
    "email",
    "url",
    "json",
]

RelationshipCardinality = Literal["one_to_one", "one_to_many", "many_to_one", "many_to_many"]


class ParseProfile(ProfilerModel):
    integer_rate: float = Field(ge=0.0, le=1.0)
    number_rate: float = Field(ge=0.0, le=1.0)
    money_rate: float = Field(ge=0.0, le=1.0)
    boolean_rate: float = Field(ge=0.0, le=1.0)
    date_rate: float = Field(ge=0.0, le=1.0)
    datetime_rate: float = Field(ge=0.0, le=1.0)
    email_rate: float = Field(ge=0.0, le=1.0)
    url_rate: float = Field(ge=0.0, le=1.0)
    json_rate: float = Field(ge=0.0, le=1.0)


class FieldCandidate(ProfilerModel):
    kind: Literal[
        "primary_key",
        "foreign_key",
        "label",
        "measure",
        "timestamp",
        "category",
        "status",
        "identifier",
    ]
    confidence: float = Field(ge=0.0, le=1.0)
    reasons: list[str] = Field(default_factory=list)


class FieldProfile(ProfilerModel):
    field_id: str
    asset_id: str
    name: str
    row_count: int
    non_null_count: int
    blank_count: int
    distinct_count: int
    null_rate: float = Field(ge=0.0, le=1.0)
    blank_rate: float = Field(ge=0.0, le=1.0)
    non_null_rate: float = Field(ge=0.0, le=1.0)
    uniqueness_rate: float = Field(ge=0.0, le=1.0)
    observed_type: ObservedType
    parse: ParseProfile
    sample_values: list[Any] = Field(default_factory=list)
    top_values: list[dict[str, Any]] = Field(default_factory=list)
    min_value: Any = None
    max_value: Any = None
    candidates: list[FieldCandidate] = Field(default_factory=list)
    quality_flags: list[str] = Field(default_factory=list)


class AssetProfile(ProfilerModel):
    asset_id: str
    qualified_name: str
    row_count: int
    field_count: int
    profiled_field_count: int
    density: float = Field(ge=0.0, le=1.0)
    primary_key_field_ids: list[str] = Field(default_factory=list)
    label_field_ids: list[str] = Field(default_factory=list)
    measure_field_ids: list[str] = Field(default_factory=list)
    timestamp_field_ids: list[str] = Field(default_factory=list)
    freshness: dict[str, Any] = Field(default_factory=dict)
    quality_flags: list[str] = Field(default_factory=list)


class RelationshipProfile(ProfilerModel):
    left_asset_id: str
    left_field_id: str
    right_asset_id: str
    right_field_id: str
    predicate: Literal["RELATIONSHIP_CANDIDATE"] = "RELATIONSHIP_CANDIDATE"
    cardinality: RelationshipCardinality
    overlap_ratio: float = Field(ge=0.0, le=1.0)
    shared_value_count: int
    confidence: float = Field(ge=0.0, le=1.0)
    sample_shared_values: list[str] = Field(default_factory=list)
    reasons: list[str] = Field(default_factory=list)


class ProfilerRunResult(ProfilerModel):
    organization_id: str
    snapshot_ids: list[str]
    asset_count: int
    field_count: int
    relationship_count: int
    quality_flags: list[str] = Field(default_factory=list)
