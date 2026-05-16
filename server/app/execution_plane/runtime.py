"""Runtime execution for compiled analysis plans."""

from __future__ import annotations

import asyncio
from uuid import UUID

from app.analysis_contracts import AnalysisGraphPlan, AnalysisResultRef
from app.data_plane.storage import safe_query
from app.execution_plane.compiler import compile_analysis_plan
from app.execution_plane.contracts import ExecutionCatalog, ExecutionRuntimeError
from app.execution_plane.guard import count_query, preview_query
from app.execution_plane.resolver import resolve_execution_catalog


async def execute_analysis_plan(
    organization_id: UUID,
    plan: AnalysisGraphPlan,
    *,
    catalog: ExecutionCatalog | None = None,
    max_preview_rows: int = 50,
) -> AnalysisResultRef:
    """Validate, compile, and execute one AnalysisGraphPlan.

    This is deterministic. It never calls an agent and never attempts to repair
    invalid plans.
    """
    resolved_catalog = catalog or await resolve_execution_catalog(organization_id, plan)
    compiled = compile_analysis_plan(plan, resolved_catalog)
    allowed_tables = set(compiled.source_tables)
    count_sql = count_query(compiled.sql, allowed_tables=allowed_tables)
    preview_sql = preview_query(
        compiled.sql,
        allowed_tables=allowed_tables,
        limit=max_preview_rows,
    )
    try:
        count_rows = await asyncio.to_thread(safe_query, organization_id, count_sql, max_rows=1)
        preview_rows = await asyncio.to_thread(safe_query, organization_id, preview_sql, max_rows=max_preview_rows)
    except Exception as exc:
        raise ExecutionRuntimeError(
            "Analysis execution failed",
            details={"graph_id": plan.graph_id, "error": str(exc)},
        ) from exc
    row_count = int(count_rows[0]["row_count"]) if count_rows else 0
    return AnalysisResultRef(
        graph_id=plan.graph_id,
        row_count=row_count,
        result_preview=preview_rows,
        lineage=[
            {
                **line,
                "graph_id": plan.graph_id,
                "output_node": compiled.output_node,
                "operation_count": compiled.operation_count,
            }
            for line in compiled.lineage
        ],
    )


async def execute_analysis_plans(
    organization_id: UUID,
    plans: list[AnalysisGraphPlan],
    *,
    max_preview_rows: int = 50,
    max_parallel: int = 3,
) -> list[AnalysisResultRef]:
    semaphore = asyncio.Semaphore(max(1, max_parallel))

    async def _one(plan: AnalysisGraphPlan) -> AnalysisResultRef:
        async with semaphore:
            return await execute_analysis_plan(
                organization_id,
                plan,
                max_preview_rows=max_preview_rows,
            )

    return list(await asyncio.gather(*[_one(plan) for plan in plans]))
