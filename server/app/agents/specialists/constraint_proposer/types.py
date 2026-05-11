"""Typed I/O for ConstraintProposer.

Per docs/40-features/AGENT-CONS.md §3.2.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field

from app.agents.specialists.cardinality_resolver.types import CardinalityDecision
from app.agents.specialists.column_classifier.types import ClassifiedColumn
from app.agents.specialists.entity_reconciler.types import EntityReconciliationPlan


__all__ = [
    "ColumnObservations",
    "ConstraintKind",
    "ConstraintProposal",
    "ConstraintProposerInput",
    "ConstraintProposerOutput",
]


class ConstraintKind(StrEnum):
    PRIMARY_KEY = "primary_key"
    UNIQUE = "unique"
    NOT_NULL = "not_null"
    CHECK_ENUM = "check_enum"
    CHECK_RANGE = "check_range"
    CHECK_POSITIVE = "check_positive"
    DEFAULT = "default"
    AUDIT_TIMESTAMP = "audit_timestamp"
    CURRENCY_CONSIST = "currency_consist"


class ColumnObservations(BaseModel):
    """Deterministic facts per column from row sampling."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    table_name: str
    column_name: str
    sample_size: int = Field(ge=0)
    null_rate: Annotated[float, Field(ge=0.0, le=1.0)]
    distinct_count: int = Field(ge=0)
    most_frequent: str | int | float | bool | None = None
    most_frequent_rate: Annotated[float, Field(ge=0.0, le=1.0)]
    observed_range: tuple[float, float] | None = None
    """Numeric range when `column` is numeric-typed; None otherwise."""
    observed_enum: list[str] | None = None
    """Set when distinct_count is small (≤ 12); the agent uses this for STATUS."""


class ConstraintProposerInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    business_context: str | None = Field(default=None, max_length=5000)
    """User-provided business context for deciding what should be constrained."""
    reconciliation_plan: EntityReconciliationPlan
    classified_columns: list[ClassifiedColumn] = Field(min_length=1)
    cardinalities: list[CardinalityDecision] = Field(default_factory=list)
    observations: list[ColumnObservations] = Field(default_factory=list)


class ConstraintProposal(BaseModel):
    """One typed proposal the deterministic compiler will emit as DDL."""

    model_config = ConfigDict(extra="forbid")
    kind: ConstraintKind
    table_name: str
    columns: list[str] = Field(min_length=1)
    enum_values: list[str] | None = None
    """Required when kind == CHECK_ENUM."""
    range_min: float | None = None
    range_max: float | None = None
    """Both required when kind == CHECK_RANGE."""
    default_value: str | int | float | bool | None = None
    """Set when kind == DEFAULT; otherwise None."""
    rationale: Annotated[str, Field(min_length=1, max_length=500)]


class ConstraintProposerOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    proposals: list[ConstraintProposal] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list, max_length=20)
