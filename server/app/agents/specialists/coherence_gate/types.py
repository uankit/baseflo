"""Typed I/O for CoherenceGate.

Per docs/40-features/AGENT-COHE.md §3.2.

This is the ONLY agent whose output is never user-surfaced as an artifact —
the agent emits a `CoherenceReport` that the manager either acts on (route
repairs / escalate) or hides (when passed=True, only the workspace.ready
event reaches the user).
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.agents.specialists.cardinality_resolver.types import CardinalityDecision
from app.agents.specialists.constraint_proposer.types import ConstraintProposal
from app.agents.specialists.entity_reconciler.types import EntityReconciliationPlan
from app.agents.specialists.kpi_planner.types import KPIDefinition
from app.engines.schema.ir import SchemaIR


__all__ = [
    "ClarificationRequest",
    "ClarificationQuestion",
    "CoherenceGateInput",
    "CoherenceGateOutput",
    "CoherenceReport",
    "CrossCuttingIssue",
    "DeterministicFinding",
    "FindingCategory",
    "IssueCategory",
    "IssueSeverity",
    "RepairRoute",
]


class IssueSeverity(StrEnum):
    BLOCKING = "blocking"
    WARNING = "warning"


class IssueCategory(StrEnum):
    KPI_COLUMN_MISSING = "kpi_column_missing"
    CARDINALITY_INCONSISTENT = "cardinality_inconsistent"
    FUNDAMENTAL_CONCEPT_MISSING = "fundamental_concept_missing"
    MERGE_STRATEGY_CONFLICT = "merge_strategy_conflict"
    CONSTRAINT_VS_SOURCE_DATA = "constraint_vs_source_data"
    PII_PROPAGATION = "pii_propagation"
    MONEY_SHAPE = "money_shape"
    OTHER = "other"


class FindingCategory(StrEnum):
    """Categories the deterministic checks emit. Mostly mirrors IssueCategory but
    keeps the helper types decoupled from the agent's typed `IssueCategory` so
    new findings can be added without renaming the agent's enum."""
    KPI_COLUMN_MISSING = "kpi_column_missing"
    RELATIONSHIP_ENDPOINT_MISSING = "relationship_endpoint_missing"
    RELATIONSHIP_MISSING = "relationship_missing"
    CARDINALITY_INCONSISTENT = "cardinality_inconsistent"
    PII_NOT_MASKED = "pii_not_masked"
    MONEY_SHAPE_INVALID = "money_shape_invalid"
    KPI_TIME_DIMENSION_INVALID = "kpi_time_dimension_invalid"
    KPI_STATUS_FILTER_INVALID = "kpi_status_filter_invalid"
    EMPTY_SCHEMA = "empty_schema"


class DeterministicFinding(BaseModel):
    """A typed structural fact the deterministic checks helper produces.

    The agent reads these as evidence and decides severity + repair routing.
    Per docs/50-design-patterns.md §8B (Evidence-Feeding pattern).
    """

    model_config = ConfigDict(frozen=True, extra="forbid")
    category: FindingCategory
    description: str = Field(min_length=1, max_length=500)
    affected_artifacts: list[str] = Field(default_factory=list)


class CrossCuttingIssue(BaseModel):
    """An issue the agent has classified for the manager to act on."""

    model_config = ConfigDict(extra="forbid")
    severity: IssueSeverity
    category: IssueCategory
    description: str = Field(min_length=1, max_length=1000)
    affected_artifacts: list[str] = Field(default_factory=list)


class RepairRoute(BaseModel):
    """A typed instruction telling the manager which specialist to re-run."""

    model_config = ConfigDict(extra="forbid")
    target_agent: str = Field(min_length=2, max_length=80)
    reason: str = Field(min_length=1, max_length=500)
    additional_context: dict[str, Any] = Field(default_factory=dict)
    """Typed payload merged into the target agent's input on the next attempt."""
    affected_artifacts: list[str] = Field(default_factory=list)


class ClarificationQuestion(BaseModel):
    model_config = ConfigDict(extra="forbid")
    text: str = Field(min_length=10, max_length=200)
    """Plain business language; the manager surfaces this through the conversation."""


class ClarificationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    questions: list[ClarificationQuestion] = Field(min_length=1, max_length=3)
    blocking: bool = True


class CoherenceReport(BaseModel):
    model_config = ConfigDict(extra="forbid")
    passed: bool
    issues: list[CrossCuttingIssue] = Field(default_factory=list)
    repair_routes: list[RepairRoute] = Field(default_factory=list, max_length=5)
    """Max 5 routes per cycle; manager applies them then re-runs the gate."""
    escalate_to_user: ClarificationRequest | None = None
    rationale: str = Field(min_length=1, max_length=2000)
    """Trace-only; never reaches the user directly."""


class CoherenceGateInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    business_context: str | None = Field(default=None, max_length=5000)
    schema_ir: SchemaIR
    kpi_definitions: list[KPIDefinition] = Field(default_factory=list)
    reconciliation_plan: EntityReconciliationPlan
    cardinalities: list[CardinalityDecision] = Field(default_factory=list)
    constraints: list[ConstraintProposal] = Field(default_factory=list)
    deterministic_findings: list[DeterministicFinding] = Field(default_factory=list)


class CoherenceGateOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    report: CoherenceReport
