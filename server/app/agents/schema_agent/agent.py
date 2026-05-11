"""SchemaAgent — AgentSpec + output validator + registration."""

from __future__ import annotations

from app.agents.registry import register_agent
from app.agents.schema_agent.prompt import INSTRUCTIONS
from app.agents.schema_agent.types import SchemaAgentInput, SchemaAgentOutput
from app.agents.types import AgentSpec, ModelTier
from app.engines.schema.compatibility import normalize_ir
from app.engines.schema.compatibility import validate as ir_validate


def _validate_output(
    output: SchemaAgentOutput,
    *,
    input_payload: SchemaAgentInput | None = None,
) -> SchemaAgentOutput:
    _ = input_payload
    ir = normalize_ir(output.schema_ir)
    report = ir_validate(ir)
    if not report.passed:
        raise ValueError(f"SchemaIR failed deterministic validation: {report.summary()}")
    for table in ir.tables:
        col_names = {c.name for c in table.columns}
        if "id" not in col_names:
            raise ValueError(f"Table {table.name!r} missing required 'id' column.")
        if table.primary_key != ["id"]:
            raise ValueError(f"Table {table.name!r} primary key must be ['id'].")
    return output.model_copy(update={"schema_ir": ir})


def _make_spec() -> AgentSpec[SchemaAgentInput, SchemaAgentOutput]:
    return AgentSpec(
        name="SchemaAgent",
        input_type=SchemaAgentInput,
        output_type=SchemaAgentOutput,
        instructions=INSTRUCTIONS,
        model_tier=ModelTier.BALANCED,
        output_validators=(_validate_output,),
    )


SPEC = register_agent(_make_spec())
