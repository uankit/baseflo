"""Neutral typed query language shared by planning and execution.

Agents may emit these contracts, but they do not own them. The Execution Plane
validates and translates this language into read-only DuckDB statements.
"""

from __future__ import annotations

from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class AnalysisContractModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class SourceOp(AnalysisContractModel):
    op: Literal["source"] = "source"
    id: str
    asset_id: str


class SelectOp(AnalysisContractModel):
    op: Literal["select"] = "select"
    id: str
    input: str
    field_ids: list[str]


class FilterPredicate(AnalysisContractModel):
    field_id: str
    operator: Literal["=", "!=", ">", ">=", "<", "<=", "is_null", "is_not_null"]
    value: str | int | float | bool | None = None


class FilterOp(AnalysisContractModel):
    op: Literal["filter"] = "filter"
    id: str
    input: str
    predicates: list[FilterPredicate]


class JoinOp(AnalysisContractModel):
    op: Literal["join"] = "join"
    id: str
    left_input: str
    right_input: str
    left_field_id: str
    right_field_id: str
    join_kind: Literal["inner", "left"] = "inner"


class AggregateMeasure(AnalysisContractModel):
    field_id: str | None = None
    aggregate: Literal["sum", "avg", "count", "min", "max"]
    alias: str


class AggregateOp(AnalysisContractModel):
    op: Literal["aggregate"] = "aggregate"
    id: str
    input: str
    group_by_field_ids: list[str]
    measures: list[AggregateMeasure]


class RankOp(AnalysisContractModel):
    op: Literal["rank"] = "rank"
    id: str
    input: str
    order_by_alias: str
    direction: Literal["asc", "desc"] = "desc"
    alias: str = "rank"


class LimitOp(AnalysisContractModel):
    op: Literal["limit"] = "limit"
    id: str
    input: str
    limit: int = Field(ge=1, le=100)


AnalysisOp = Annotated[
    SourceOp | SelectOp | FilterOp | JoinOp | AggregateOp | RankOp | LimitOp,
    Field(discriminator="op"),
]


class AnalysisGraphPlan(AnalysisContractModel):
    agent: Literal["Instantiator"] = "Instantiator"
    graph_id: str
    hypothesis_id: str
    operators: list[AnalysisOp]
    output: str
    audience: dict[str, Any] = Field(default_factory=dict)
    why: str


class AnalysisResultRef(AnalysisContractModel):
    graph_id: str
    row_count: int
    result_preview: list[dict[str, Any]]
    lineage: list[dict[str, Any]] = Field(default_factory=list)
