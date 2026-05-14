"""Per-org analytical substrate backed by DuckDB.

One DuckDB file per organization at `{data_dir}/duckdb/{org_id}.duckdb`. Each
connected source contributes one table per discovered table (e.g., one per
Google Sheet tab), named `{source_slug}__{table_slug}`.

For v1: full-refresh sync (drop + recreate per table). Incremental sync via
watermark columns comes later.

This module is the analytical *plane*. Postgres remains the control plane
(orgs, users, KPI defs, audit). DuckDB is where the raw mirrored data lives so
analytical queries are fast.
"""

from __future__ import annotations

import asyncio
import re
from pathlib import Path
from typing import Any
from uuid import UUID

import duckdb

from app.config import get_settings
from app.core.errors import ValidationError
from app.db.models import Connection, DataSource
from app.sources import get_source_instance
from connectors import SourceQuery

_settings = get_settings()
_DATA_ROOT = Path(_settings.data_dir).expanduser().resolve() / "duckdb"
_DATA_ROOT.mkdir(parents=True, exist_ok=True)

_SAFE_SQL = re.compile(r"^\s*(SELECT|WITH)\s", re.IGNORECASE | re.DOTALL)
_SLUG_RE = re.compile(r"[^a-z0-9]+")


def _db_path(org_id: UUID) -> Path:
    return _DATA_ROOT / f"{org_id}.duckdb"


def _open(org_id: UUID, *, read_only: bool) -> duckdb.DuckDBPyConnection:
    return duckdb.connect(str(_db_path(org_id)), read_only=read_only)


def _slug(name: str) -> str:
    s = _SLUG_RE.sub("_", name.lower()).strip("_")
    return s or "untitled"


def _quote_ident(value: str) -> str:
    return '"' + value.replace('"', '""') + '"'


def _clean_column_name(value: Any, index: int) -> str:
    text = str(value).strip() if value is not None else ""
    return text or f"column_{index + 1}"


def _unique_column_names(values: list[Any]) -> list[str]:
    names: list[str] = []
    seen: dict[str, int] = {}
    for index, value in enumerate(values):
        base = _clean_column_name(value, index)
        count = seen.get(base, 0) + 1
        seen[base] = count
        names.append(base if count == 1 else f"{base}_{count}")
    return names


def qualified_name(source_name: str, table_name: str) -> str:
    """Deterministic DuckDB table name for a (source, table) pair."""
    return f"{_slug(source_name)}__{_slug(table_name)}"


async def sync_data_source(
    ds: DataSource, connection: Connection,
) -> dict[str, int]:
    """Mirror source rows into the org's DuckDB. Returns {qualified_name: rows_written}."""
    source = get_source_instance(ds.kind)
    refreshed = await source.authenticate({"credentials": connection.credentials})
    credentials = refreshed["credentials"]

    schema = ds.discovered_schema or {}
    results: dict[str, int] = {}

    def _open_rw() -> duckdb.DuckDBPyConnection:
        return _open(ds.organization_id, read_only=False)

    db = await asyncio.to_thread(_open_rw)
    try:
        for table_info in schema.get("tables", []):
            table_name = table_info["name"]
            label = table_info["label"]
            columns = _unique_column_names([c["name"] for c in table_info["columns"]])
            if not columns:
                continue

            qname = qualified_name(ds.name, table_name)
            cols_def = ", ".join(f"{_quote_ident(c)} VARCHAR" for c in columns)
            placeholders = ", ".join(["?"] * len(columns))

            def _recreate(q: str = qname, defs: str = cols_def) -> None:
                quoted = _quote_ident(q)
                db.execute(f"DROP TABLE IF EXISTS {quoted}")
                db.execute(f"CREATE TABLE {quoted} ({defs})")

            await asyncio.to_thread(_recreate)

            config = {**ds.config, "credentials": credentials}
            query = SourceQuery(table=table_name, label=label)

            batch: list[list[Any]] = []
            total = 0

            def _flush(
                rows: list[list[Any]], q: str = qname, ph: str = placeholders,
            ) -> int:
                if not rows:
                    return 0
                db.executemany(f"INSERT INTO {_quote_ident(q)} VALUES ({ph})", rows)
                return len(rows)

            async for row in source.read(config, query):
                batch.append([row.values.get(c) for c in columns])
                if len(batch) >= 500:
                    total += await asyncio.to_thread(_flush, batch)
                    batch = []
            if batch:
                total += await asyncio.to_thread(_flush, batch)

            results[qname] = total
    finally:
        await asyncio.to_thread(db.close)

    return results


def safe_query(
    org_id: UUID, sql: str, *, max_rows: int = 1000,
) -> list[dict[str, Any]]:
    """Run a validated read-only SELECT against an org's substrate."""
    if not _SAFE_SQL.match(sql):
        raise ValidationError(
            message="Only SELECT/WITH statements are allowed",
            code="SQL_NOT_SELECT",
            status_hint=400,
        )

    db = _open(org_id, read_only=True)
    try:
        cur = db.execute(sql)
        rows = cur.fetchmany(max_rows)
        cols = [d[0] for d in cur.description] if cur.description else []
        return [dict(zip(cols, row)) for row in rows]
    finally:
        db.close()


def list_substrate_tables(org_id: UUID) -> list[dict[str, Any]]:
    """List all tables present in the org's substrate (cheap metadata query)."""
    if not _db_path(org_id).exists():
        return []
    db = _open(org_id, read_only=True)
    try:
        cur = db.execute(
            """
            SELECT t.table_name,
                   (SELECT count(*) FROM information_schema.columns c
                    WHERE c.table_name = t.table_name) AS column_count
            FROM information_schema.tables t
            WHERE t.table_schema = 'main'
            ORDER BY t.table_name
            """
        )
        return [
            {"qualified_name": r[0], "column_count": r[1]}
            for r in cur.fetchall()
        ]
    finally:
        db.close()
