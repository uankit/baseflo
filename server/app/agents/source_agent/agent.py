"""SourceAgent — AgentSpec + output validator + registration."""

from __future__ import annotations

from app.agents.registry import register_agent
from app.agents.source_agent.prompt import INSTRUCTIONS
from app.agents.source_agent.types import SourceAgentInput, SourceAgentOutput
from app.agents.types import AgentSpec, ModelTier


def _validate_output(
    output: SourceAgentOutput,
    *,
    input_payload: SourceAgentInput | None = None,
) -> SourceAgentOutput:
    _ = input_payload
    sm = output.source_map
    if not sm.tables:
        raise ValueError("SourceMap must contain at least one table.")
    for table in sm.tables:
        if not table.columns:
            raise ValueError(f"Table {table.name!r} has no columns.")
        if table.primary_key:
            pk_set = set(table.primary_key)
            col_names = {c.name for c in table.columns}
            missing = pk_set - col_names
            if missing:
                raise ValueError(
                    f"Table {table.name!r} primary key references missing columns: {missing}"
                )
    return output


def _make_spec() -> AgentSpec[SourceAgentInput, SourceAgentOutput]:
    return AgentSpec(
        name="SourceAgent",
        input_type=SourceAgentInput,
        output_type=SourceAgentOutput,
        instructions=INSTRUCTIONS,
        model_tier=ModelTier.BALANCED,
        output_validators=(_validate_output,),
    )


SPEC = register_agent(_make_spec())
