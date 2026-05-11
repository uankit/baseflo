"""InsightAgent — AgentSpec + output validator + registration."""

from __future__ import annotations

from app.agents.registry import register_agent
from app.agents.insight_agent.prompt import INSTRUCTIONS
from app.agents.insight_agent.types import InsightAgentInput, InsightAgentOutput
from app.agents.types import AgentSpec, ModelTier


def _validate_output(
    output: InsightAgentOutput,
    *,
    input_payload: InsightAgentInput | None = None,
) -> InsightAgentOutput:
    _ = input_payload
    board = output.insight_board
    if not board.kpis and not board.segments and not board.anomalies:
        raise ValueError(
            "InsightBoard must contain at least one KPI, segment, or anomaly."
        )
    for kpi in board.kpis:
        if kpi.sql and not kpi.sql.strip().upper().startswith("SELECT"):
            raise ValueError(f"KPI {kpi.kpi_id!r} SQL must start with SELECT.")
    return output


def _make_spec() -> AgentSpec[InsightAgentInput, InsightAgentOutput]:
    return AgentSpec(
        name="InsightAgent",
        input_type=InsightAgentInput,
        output_type=InsightAgentOutput,
        instructions=INSTRUCTIONS,
        model_tier=ModelTier.REASONING,
        output_validators=(_validate_output,),
    )


SPEC = register_agent(_make_spec())
