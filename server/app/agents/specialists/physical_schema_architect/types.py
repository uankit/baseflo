"""Typed I/O for PhysicalSchemaArchitect.

Per docs/40-features/AGENT-PHYS.md §3.2.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from app.agents.specialists.cardinality_resolver.types import CardinalityDecision
from app.agents.specialists.column_classifier.types import ClassifiedColumn
from app.agents.specialists.constraint_proposer.types import ConstraintProposal
from app.agents.specialists.entity_reconciler.types import EntityReconciliationPlan
from app.engines.schema.ir import SchemaIR


__all__ = [
    "PhysicalSchemaArchitectInput",
    "PhysicalSchemaArchitectOutput",
]


class PhysicalSchemaArchitectInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    business_context: str | None = Field(default=None, max_length=5000)
    """User-provided business context for schema naming and grain choices."""
    reconciliation_plan: EntityReconciliationPlan
    classified_columns: list[ClassifiedColumn] = Field(min_length=1)
    cardinalities: list[CardinalityDecision] = Field(default_factory=list)
    constraints: list[ConstraintProposal] = Field(default_factory=list)
    parent_ir: SchemaIR | None = None
    """For refinement: the parent version to preserve identity ids against."""


class PhysicalSchemaArchitectOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_ir: SchemaIR
    composition_notes: list[str] = Field(default_factory=list, max_length=50)
    """Trace-only; explains decisions like 'renamed Stripe.customers → customer_billing'."""
