"""Typed I/O for CardinalityResolver.

Per docs/40-features/AGENT-CARD.md §3.2.
"""

from __future__ import annotations

from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field

from app.agents.specialists.entity_reconciler.types import EntityReconciliationPlan
from app.engines.schema.enums import Cardinality, OnDelete, SemanticType


__all__ = [
    "CardinalityDecision",
    "CardinalityResolverInput",
    "CardinalityResolverOutput",
    "FKCandidate",
    "FKDistribution",
]


class FKDistribution(BaseModel):
    """Deterministic row-distribution facts for one candidate FK pair.

    Computed by `evidence.compute_fk_distributions`. The agent reads these as
    typed facts to decide cardinality direction and on_delete.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    distinct_from_values: int = Field(ge=0)
    distinct_to_values: int = Field(ge=0)
    nulls_in_from: int = Field(ge=0)
    average_rows_per_referenced_to: float = Field(ge=0.0)
    """Mean reference frequency for each value in the to-side."""
    sample_size: int = Field(ge=0)


class FKCandidate(BaseModel):
    """A potential foreign-key relationship between two columns."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str = Field(min_length=2, max_length=120)
    """Stable identifier the agent uses to match decisions back to candidates."""
    from_table: str
    from_column: str
    to_table: str
    to_column: str
    semantic_type_from: SemanticType
    semantic_type_to: SemanticType
    distribution: FKDistribution


class CardinalityResolverInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    business_context: str | None = Field(default=None, max_length=5000)
    reconciliation_plan: EntityReconciliationPlan
    fk_candidates: list[FKCandidate] = Field(default_factory=list)


class CardinalityDecision(BaseModel):
    """Typed decision the compiler consumes when emitting relationships."""

    model_config = ConfigDict(extra="forbid")

    relationship_name: str = Field(pattern=r"^[a-z][a-z0-9_]*$", min_length=2, max_length=80)
    candidate_name: str
    """References `FKCandidate.name`; lets compilers and validators round-trip."""
    from_table: str
    from_columns: list[str] = Field(min_length=1)
    to_table: str
    to_columns: list[str] = Field(min_length=1)
    cardinality: Cardinality
    optional_from: bool = False
    optional_to: bool = False
    on_delete: OnDelete = OnDelete.RESTRICT
    join_table_name: str | None = None
    """Required when cardinality == MANY_TO_MANY; agent picks alphabetically-named bridge."""
    rationale: Annotated[str, Field(min_length=1, max_length=500)]


class CardinalityResolverOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    decisions: list[CardinalityDecision] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list, max_length=20)
