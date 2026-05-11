"""Typed I/O for ColumnClassifier.

Per docs/40-features/AGENT-COL.md §3.2. The IR enums are imported directly so
the classifier's output uses the same `SemanticType` / `PhysicalType` values
the deterministic compilers expect — no translation layer needed.
"""

from __future__ import annotations

from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field

from app.engines.profiling import SourceEvidenceBundle  # noqa: TC001
from app.engines.schema.enums import (
    PII_SEMANTIC_TYPES,
    PhysicalType,
    SemanticType,
)

# Public re-export so callers can import from one place.
__all__ = [
    "PII_SEMANTIC_TYPES",
    "ClassifiedColumn",
    "ColumnClassifierInput",
    "ColumnClassifierOutput",
    "SampleColumn",
    "SampleTable",
]


SampleValue = str | int | float | bool | None


class SampleColumn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=255)
    """Column name as the source reports it (NOT canonicalized yet)."""
    source_type: str = Field(min_length=1, max_length=120)
    """Connector's native type string (e.g., 'integer', 'jsonb', 'varchar')."""
    nullable: bool
    sample_values: list[SampleValue] = Field(default_factory=list, max_length=50)
    description: str | None = Field(default=None, max_length=2000)
    primary_key_member: bool = False


class SampleTable(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=255)
    columns: list[SampleColumn] = Field(min_length=1)
    estimated_row_count: int | None = Field(default=None, ge=0)


class ColumnClassifierInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    connector_name: str = Field(min_length=2, max_length=64)
    source_name: str = Field(min_length=1, max_length=200)
    """Human-friendly source name shown to the user."""
    business_context: str | None = Field(default=None, max_length=5000)
    """User-provided business context. Evidence for semantics, not a hard rule."""
    evidence_profile: SourceEvidenceBundle | None = None
    """Deterministic profile facts for this source. Agents should prefer these
    aggregate observations over raw sample values when classifying columns."""
    tables: list[SampleTable] = Field(min_length=1)


class ClassifiedColumn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    table_name: str
    column_name: str
    canonical_name: str = Field(pattern=r"^[a-z][a-z0-9_]*$", min_length=1, max_length=63)
    label: str = Field(min_length=1, max_length=200)
    semantic_type: SemanticType
    physical_type: PhysicalType
    nullable: bool
    confidence: Annotated[float, Field(ge=0.0, le=1.0)]
    rationale: str = Field(min_length=1, max_length=1000)
    """Trace-only; never user-surfaced."""
    pii_masked_by_default: bool = False
    enum_values: list[str] | None = None
    """Required when semantic_type == STATUS."""
    currency: str | None = Field(default=None, pattern=r"^[A-Z]{3}$|^$")
    """ISO-4217 code when ALL observed rows share one currency. Mutually
    exclusive with `currency_column`. Both may be None when currency context
    cannot be inferred from observations — surfaced as a workspace assumption."""
    currency_column: str | None = Field(
        default=None, pattern=r"^[a-z][a-z0-9_]*$", max_length=63
    )
    """Sibling column (canonical name) on the same table that holds the per-row
    ISO currency code. Set when the source data has a dedicated currency column
    AND observations show >1 distinct currency value. Mutually exclusive with
    `currency` field above."""
    is_minor_unit: bool = False
    minor_unit_assumption: str | None = Field(default=None, max_length=500)
    """Plain English (e.g., 'Stripe-style cents'). Required when semantic_type == MONEY."""


class ColumnClassifierOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    classified: list[ClassifiedColumn] = Field(min_length=1)
    assumptions: list[str] = Field(default_factory=list, max_length=20)
    """Cross-cutting assumptions surfaced for the workspace ('USD assumed for all money')."""
