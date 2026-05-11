"""Typed I/O for ImpactAnalyzer.

Per docs/40-features/AGENT-IMP.md §3.2. Given the typed intents from
IntentInterpreter + the current IR, decides which downstream artifacts
will change. The output is structured so ChangePlanner can act on it
without reading the raw IR again.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

from app.agents.specialists.intent_interpreter.types import RefinementIntent
from app.agents.specialists.kpi_planner.types import KPIDefinition
from app.engines.schema.ir import SchemaIR


class ImpactSeverity(StrEnum):
    """How disruptive the change is."""
    NON_BREAKING = "non_breaking"
    """Schema additions, KPI additions — child IR is a superset of parent."""
    BREAKING = "breaking"
    """Renames, drops, type changes — existing rows / dashboards break."""


class ImpactedArtifact(BaseModel):
    """A single thing that needs to change."""

    model_config = ConfigDict(extra="forbid")
    artifact_kind: str = Field(min_length=2, max_length=80)
    """One of: 'table', 'column', 'relationship', 'kpi', 'admin_widget'."""
    name: str = Field(min_length=1, max_length=200)
    change: str = Field(min_length=2, max_length=80)
    """One of: 'add', 'remove', 'rename', 'modify'."""
    detail: str = Field(min_length=1, max_length=500)
    """Plain-English explanation. The diff renderer surfaces this verbatim."""


class ImpactAnalyzerInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    intents: list[RefinementIntent] = Field(min_length=1, max_length=5)
    parent_ir: SchemaIR
    parent_kpis: list[KPIDefinition] = Field(default_factory=list, max_length=12)


class ImpactAnalysis(BaseModel):
    """Per-intent assessment of what changes."""

    model_config = ConfigDict(extra="forbid")
    intent_index: int = Field(ge=0)
    """Index into the input's `intents` list. Lets the planner correlate."""
    severity: ImpactSeverity
    affected_artifacts: list[ImpactedArtifact] = Field(min_length=1, max_length=20)
    requires_data_migration: bool
    """True iff existing tenant rows need to be transformed (e.g., column
    renames, type changes)."""
    rationale: str = Field(min_length=1, max_length=1000)


class ImpactAnalyzerOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    analyses: list[ImpactAnalysis] = Field(min_length=1, max_length=5)
    overall_severity: ImpactSeverity
    """Worst case across all intents — drives whether the orchestrator
    asks the user to confirm."""
    summary: str = Field(min_length=1, max_length=2000)
    """Plain-English overview the user reads on the diff screen."""
