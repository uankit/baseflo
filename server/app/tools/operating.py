"""Operating intelligence tools for the LLM orchestrator."""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, Field
from sqlalchemy import select

from app.agentic import AnalysisGraph, AnalysisRuntime
from app.core.context import TenantCtx
from app.db.models import OperatingAsset, OperatingColumn
from app.db.session import open_session
from app.intelligence import RememberInput, read_operating_brief, remember
from app.tools import Tool, register


class GetOperatingBriefInput(BaseModel):
    include_assets: bool = True
    include_metrics: bool = True
    include_insights: bool = True
    include_memories: bool = True
    include_actions: bool = True


async def _get_operating_brief_run(
    inp: GetOperatingBriefInput, ctx: TenantCtx,
) -> dict[str, object]:
    brief = await read_operating_brief(ctx)
    data = brief.model_dump()
    if not inp.include_assets:
        data["assets"] = []
        data["relationships"] = []
    if not inp.include_metrics:
        data["metrics"] = []
    if not inp.include_insights:
        data["insights"] = []
    if not inp.include_memories:
        data["memories"] = []
    if not inp.include_actions:
        data["actions"] = []
    return data


register(Tool(
    name="get_operating_brief",
    description=(
        "Read Baseflo's current operating model: discovered assets, relationship "
        "candidates, grounded metrics, open insights, memories, and proposed actions."
    ),
    input_schema=GetOperatingBriefInput,
    run=_get_operating_brief_run,
))


async def _execute_analysis_graph_run(
    inp: AnalysisGraph, ctx: TenantCtx,
) -> dict[str, object]:
    async with open_session() as session:
        assets = list(
            (
                await session.execute(
                    select(OperatingAsset).where(
                        OperatingAsset.organization_id == ctx.organization_id
                    )
                )
            )
            .scalars()
            .all()
        )
        columns = list(
            (
                await session.execute(
                    select(OperatingColumn).where(
                        OperatingColumn.organization_id == ctx.organization_id
                    )
                )
            )
            .scalars()
            .all()
        )
    columns_by_asset: dict[UUID, list[OperatingColumn]] = {}
    for column in columns:
        columns_by_asset.setdefault(column.asset_id, []).append(column)
    runtime = AnalysisRuntime(assets=assets, columns_by_asset=columns_by_asset)
    result = await runtime.execute(ctx, inp)
    return result.model_dump(mode="json")


register(Tool(
    name="execute_analysis_graph",
    description=(
        "Execute a typed Baseflo AnalysisGraph. Use this instead of SQL. "
        "The graph may select a source, filter, aggregate, rank, project, and limit; "
        "the runtime validates identifiers and compiles the graph safely."
    ),
    input_schema=AnalysisGraph,
    run=_execute_analysis_graph_run,
))


class RememberInputTool(BaseModel):
    key: str = Field(description="Stable snake_case memory key.")
    value: str = Field(description="Business meaning or user preference to remember.")


async def _remember_run(inp: RememberInputTool, ctx: TenantCtx) -> dict[str, object]:
    return await remember(ctx, RememberInput(key=inp.key, value=inp.value))


register(Tool(
    name="remember",
    description=(
        "Persist a confirmed business definition or preference for future analysis. "
        "Use only when the user explicitly confirms a meaning or decision."
    ),
    input_schema=RememberInputTool,
    run=_remember_run,
))
