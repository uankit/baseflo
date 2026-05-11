"""ReconciliationAgent — AgentSpec + output validator + registration."""

from __future__ import annotations

from app.agents.registry import register_agent
from app.agents.reconciliation_agent.prompt import INSTRUCTIONS
from app.agents.reconciliation_agent.types import (
    ReconciliationAgentInput,
    ReconciliationAgentOutput,
)
from app.agents.types import AgentSpec, ModelTier


def _validate_output(
    output: ReconciliationAgentOutput,
    *,
    input_payload: ReconciliationAgentInput | None = None,
) -> ReconciliationAgentOutput:
    _ = input_payload
    eg = output.entity_graph
    if not eg.entities and not eg.unresolved:
        raise ValueError("EntityGraph must contain at least one entity or unresolved mapping.")
    canonical_ids = {e.canonical_id for e in eg.entities}
    for e in eg.entities:
        for src in e.sources:
            if src.canonical_id not in canonical_ids:
                raise ValueError(
                    f"SourceMapping canonical_id {src.canonical_id} not found in entities."
                )
    return output


def _make_spec() -> AgentSpec[ReconciliationAgentInput, ReconciliationAgentOutput]:
    return AgentSpec(
        name="ReconciliationAgent",
        input_type=ReconciliationAgentInput,
        output_type=ReconciliationAgentOutput,
        instructions=INSTRUCTIONS,
        model_tier=ModelTier.REASONING,
        output_validators=(_validate_output,),
    )


SPEC = register_agent(_make_spec())
