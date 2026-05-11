"""Typed I/O for ChangePlanner.

Per docs/40-features/AGENT-CHG.md §3.2. Emits a typed `ChangePlan` of IR
mutations the saga applies deterministically. The plan is the audit trail
for what the refinement actually did.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.agents.specialists.impact_analyzer.types import (
    ImpactAnalysis,
)
from app.agents.specialists.intent_interpreter.types import RefinementIntent
from app.engines.schema.ir import SchemaIR


class MutationKind(StrEnum):
    """One typed IR-level mutation."""

    ADD_TABLE = "add_table"
    REMOVE_TABLE = "remove_table"
    ADD_COLUMN = "add_column"
    REMOVE_COLUMN = "remove_column"
    RENAME_COLUMN = "rename_column"
    ADD_RELATIONSHIP = "add_relationship"
    REMOVE_RELATIONSHIP = "remove_relationship"


class IRMutation(BaseModel):
    """A single typed mutation against the parent IR.

    The saga applies these in order; failures roll back to the parent IR.
    `payload` carries kind-specific typed data — for ADD_TABLE that's a
    serialised `TableIR`; for RENAME_COLUMN it's `{old_name, new_name}`; etc.
    """

    model_config = ConfigDict(extra="forbid")
    kind: MutationKind
    target: str = Field(min_length=1, max_length=200)
    payload: dict[str, Any] = Field(default_factory=dict)
    rationale: str = Field(min_length=1, max_length=500)


class ChangePlannerInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    intents: list[RefinementIntent] = Field(min_length=1, max_length=5)
    impact: list[ImpactAnalysis] = Field(min_length=1, max_length=5)
    parent_ir: SchemaIR


class ChangePlan(BaseModel):
    """The typed mutation list. The saga walks it deterministically."""

    model_config = ConfigDict(extra="forbid")
    mutations: list[IRMutation] = Field(min_length=1, max_length=30)
    """Cap at 30 — refinements bigger than this go through a separate
    one-shot generation flow."""
    diff_summary: str = Field(min_length=1, max_length=2000)
    """Plain-English diff the user confirms. Lines per mutation."""
    requires_user_confirmation: bool
    """True iff overall severity was BREAKING."""


class ChangePlannerOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    plan: ChangePlan
