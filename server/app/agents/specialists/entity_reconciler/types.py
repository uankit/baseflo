"""Typed I/O for EntityReconciler.

Per docs/40-features/AGENT-ENT.md §3.2.

Reuses `SourceRef`, `JoinKey` from `app.engines.schema.ir` and the role/merge
enums from `app.engines.schema.enums` to ensure the reconciler's output flows
straight into `PhysicalSchemaArchitect` without translation.
"""

from __future__ import annotations

from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field

from app.agents.specialists.column_classifier.types import ClassifiedColumn
from app.engines.schema.enums import MergeStrategy, PrimaryKeyStrategy, SourceRole
from app.engines.schema.ir import IDENTIFIER_PATTERN, JoinKey, SourceRef


__all__ = [
    "Ambiguity",
    "AmbiguityOption",
    "ClassifiedSource",
    "ColumnMapping",
    "ConflictPolicy",
    "ContributingSource",
    "EntityReconcilerInput",
    "EntityReconciliationPlan",
    "EntityReconcilerOutput",
    "OverlapStat",
    "ReconciledEntity",
    "SourceColumnContribution",
    "UnreconciledTable",
]


# ---------- Inputs ----------


class ClassifiedSource(BaseModel):
    """One source's columns after `ColumnClassifier` ran on it."""

    model_config = ConfigDict(extra="forbid")
    connector_name: str = Field(min_length=2, max_length=64)
    source_name: str = Field(min_length=1, max_length=200)
    classified_columns: list[ClassifiedColumn] = Field(min_length=1)


class OverlapStat(BaseModel):
    """Deterministic value-overlap signal between two candidate join keys.

    Computed by `evidence.compute_overlap_stats` (M1.2 lights it up against
    real connector samples; in M1 with no connected sources the list is empty).

    These are FACTS — the agent reads them as evidence, not opinion.
    """

    model_config = ConfigDict(extra="forbid")
    source_a: SourceRef
    source_b: SourceRef
    candidate_key_a: str = Field(min_length=1, max_length=63)
    candidate_key_b: str = Field(min_length=1, max_length=63)
    sample_match_rate: Annotated[float, Field(ge=0.0, le=1.0)]
    sample_size: int = Field(ge=0)


class EntityReconcilerInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    business_context: str | None = Field(default=None, max_length=5000)
    """User-provided business context for naming and merge intent."""
    classified_sources: list[ClassifiedSource] = Field(min_length=1)
    overlap_stats: list[OverlapStat] = Field(default_factory=list)


# ---------- Outputs ----------


class SourceColumnContribution(BaseModel):
    """How a particular source column feeds a reconciled column."""

    model_config = ConfigDict(extra="forbid")
    connector_name: str
    source_table: str
    source_column: str
    confidence: Annotated[float, Field(ge=0.0, le=1.0)]


class ColumnMapping(BaseModel):
    """A canonical column on the unified entity, with all contributing sources."""

    model_config = ConfigDict(extra="forbid")
    canonical_name: str = Field(pattern=IDENTIFIER_PATTERN, min_length=1, max_length=63)
    contributions: list[SourceColumnContribution] = Field(min_length=1)


class ContributingSource(BaseModel):
    model_config = ConfigDict(extra="forbid")
    connector_name: str
    source_table: str
    role: SourceRole = SourceRole.AUGMENTING


class ConflictPolicy(BaseModel):
    """Per canonical column, which source wins when fields disagree."""

    model_config = ConfigDict(extra="forbid")
    authoritative_source: dict[str, str] = Field(default_factory=dict)
    """Map: canonical_column_name → connector_name."""
    rationale: dict[str, str] = Field(default_factory=dict)
    """Map: canonical_column_name → short reason for that authoritativeness."""


class ReconciledEntity(BaseModel):
    model_config = ConfigDict(extra="forbid")
    canonical_name: str = Field(pattern=r"^[A-Z][a-zA-Z0-9]*$", min_length=2, max_length=80)
    """PascalCase business noun: 'Customer', 'Order', 'BookingSession'."""
    canonical_table_name: str = Field(pattern=IDENTIFIER_PATTERN, min_length=1, max_length=63)
    """snake_case database identifier derived from canonical_name."""
    label: str = Field(min_length=1, max_length=200)
    contributing_sources: list[ContributingSource] = Field(min_length=1)
    column_mappings: list[ColumnMapping] = Field(min_length=1)
    join_keys: list[JoinKey] = Field(default_factory=list)
    conflict_policy: ConflictPolicy = Field(default_factory=ConflictPolicy)
    merge_strategy: MergeStrategy = MergeStrategy.PREFERRED_SOURCE
    primary_key_strategy: PrimaryKeyStrategy = PrimaryKeyStrategy.GENERATED_UUID


class UnreconciledTable(BaseModel):
    """A source table that doesn't merge with anything else.

    NOT a failure — single-source projects produce all-unreconciled entities,
    and that's the correct shape.
    """

    model_config = ConfigDict(extra="forbid")
    connector_name: str
    source_table: str
    canonical_table_name: str = Field(pattern=IDENTIFIER_PATTERN)
    label: str = Field(min_length=1, max_length=200)


class AmbiguityOption(BaseModel):
    model_config = ConfigDict(extra="forbid")
    label: str = Field(min_length=1, max_length=120)
    description: str = Field(min_length=1, max_length=500)


class Ambiguity(BaseModel):
    """When the agent is unsure between two interpretations.

    The manager decides whether to escalate to a clarification or accept with
    `recommended` as an explicit assumption.
    """

    model_config = ConfigDict(extra="forbid")
    target: str = Field(min_length=1, max_length=200)
    description: str = Field(min_length=1, max_length=1000)
    options: list[AmbiguityOption] = Field(min_length=2, max_length=4)
    recommended: int = Field(ge=0)
    """Index into `options`; the agent's preferred resolution if forced."""
    recommendation_confidence: Annotated[float, Field(ge=0.0, le=1.0)]


class EntityReconciliationPlan(BaseModel):
    """The full plan downstream agents and compilers consume."""

    model_config = ConfigDict(extra="forbid")
    reconciled_entities: list[ReconciledEntity] = Field(default_factory=list)
    unreconciled_tables: list[UnreconciledTable] = Field(default_factory=list)
    ambiguities: list[Ambiguity] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list, max_length=20)


class EntityReconcilerOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    plan: EntityReconciliationPlan
