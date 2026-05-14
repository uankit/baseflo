"""Generic data primitives. These compose into any analysis.

Two tools:
  - list_assets:   what tables are available + their columns
  - profile_asset: row count + column types of one table

The orchestrator typically calls list_assets first, then either profile_asset
or `execute_analysis_graph` from the operating tools. Raw SQL is kept as an
internal runtime primitive and is not registered as an LLM tool.
"""

from __future__ import annotations

import asyncio
import re
from typing import Any

from pydantic import BaseModel, Field
from sqlalchemy import select

from app.core.context import TenantCtx
from app.core.errors import ValidationError
from app.db.models import DataSource
from app.db.session import open_session
from app.substrate import (
    list_substrate_tables,
    qualified_name,
    safe_query,
)
from app.tools import Tool, register

_NAME_RE = re.compile(r"^[a-z0-9_]+$")


# ---------- query ----------


class QueryInput(BaseModel):
    sql: str = Field(
        description=(
            "A read-only SELECT (or WITH) statement against the organization's "
            "substrate. Reference tables by qualified_name returned by list_assets."
        )
    )
    max_rows: int = Field(default=100, ge=1, le=10000)


async def _query_run(inp: QueryInput, ctx: TenantCtx) -> dict[str, Any]:
    rows = await asyncio.to_thread(
        safe_query, ctx.organization_id, inp.sql, max_rows=inp.max_rows,
    )
    return {"rows": rows, "row_count": len(rows)}


# Intentionally not registered as an LLM tool. Agents must emit typed
# AnalysisGraph plans; only the deterministic runtime compiles SQL.


# ---------- list_assets ----------


class ListAssetsInput(BaseModel):
    pass


async def _list_assets_run(
    inp: ListAssetsInput, ctx: TenantCtx,
) -> dict[str, Any]:
    async with open_session() as session:
        result = await session.execute(
            select(DataSource).where(
                DataSource.organization_id == ctx.organization_id,
            )
        )
        sources = list(result.scalars().all())

    substrate_tables = await asyncio.to_thread(
        list_substrate_tables, ctx.organization_id,
    )
    in_substrate = {t["qualified_name"] for t in substrate_tables}

    assets: list[dict[str, Any]] = []
    for ds in sources:
        schema = ds.discovered_schema or {}
        for table_info in schema.get("tables", []):
            qname = qualified_name(ds.name, table_info["name"])
            assets.append({
                "qualified_name": qname,
                "source_name": ds.name,
                "source_id": str(ds.id),
                "table_label": table_info["label"],
                "columns": [
                    {"name": c["name"], "type": c["data_type"]}
                    for c in table_info["columns"]
                ],
                "in_substrate": qname in in_substrate,
                "last_synced_at": (
                    ds.last_synced_at.isoformat() if ds.last_synced_at else None
                ),
            })
    return {"assets": assets, "count": len(assets)}


register(Tool(
    name="list_assets",
    description=(
        "List all tables available to query, with column metadata. Always "
        "call this first when you don't know what data exists."
    ),
    input_schema=ListAssetsInput,
    run=_list_assets_run,
))


# ---------- profile_asset ----------


class ProfileAssetInput(BaseModel):
    qualified_name: str = Field(
        description=(
            "Table name as returned by list_assets (e.g., 'customers__contacts')."
        )
    )


async def _profile_asset_run(
    inp: ProfileAssetInput, ctx: TenantCtx,
) -> dict[str, Any]:
    if not _NAME_RE.match(inp.qualified_name):
        raise ValidationError(
            message="qualified_name must match [a-z0-9_]+",
            code="INVALID_TABLE_NAME",
            status_hint=400,
        )

    cols_sql = (
        f"SELECT column_name, data_type "
        f"FROM information_schema.columns "
        f"WHERE table_name = '{inp.qualified_name}' "
        f"ORDER BY ordinal_position"
    )
    columns = await asyncio.to_thread(
        safe_query, ctx.organization_id, cols_sql, max_rows=1000,
    )

    if not columns:
        return {"qualified_name": inp.qualified_name, "exists": False}

    row_count_rows = await asyncio.to_thread(
        safe_query,
        ctx.organization_id,
        f'SELECT count(*) AS n FROM "{inp.qualified_name}"',
        max_rows=1,
    )
    row_count = row_count_rows[0]["n"] if row_count_rows else 0

    return {
        "qualified_name": inp.qualified_name,
        "exists": True,
        "row_count": row_count,
        "columns": columns,
    }


register(Tool(
    name="profile_asset",
    description=(
        "Get column types and row count for a specific table in the substrate."
    ),
    input_schema=ProfileAssetInput,
    run=_profile_asset_run,
))
