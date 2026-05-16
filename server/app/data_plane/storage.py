"""DuckDB storage adapter for the canonical data plane."""

from __future__ import annotations

import asyncio
import re
from pathlib import Path
from typing import Any
from uuid import UUID

import duckdb

from app.config import get_settings
from app.core.errors import ValidationError
from app.data_plane.naming import quote_ident

_settings = get_settings()
_DATA_ROOT = Path(_settings.data_dir).expanduser().resolve() / "duckdb"
_DATA_ROOT.mkdir(parents=True, exist_ok=True)

_SAFE_SQL = re.compile(r"^\s*(SELECT|WITH)\s", re.IGNORECASE | re.DOTALL)


def db_path(org_id: UUID) -> Path:
    return _DATA_ROOT / f"{org_id}.duckdb"


def open_duckdb(org_id: UUID, *, read_only: bool) -> duckdb.DuckDBPyConnection:
    return duckdb.connect(str(db_path(org_id)), read_only=read_only)


class CanonicalDuckDBWriter:
    """Small async wrapper around one org's DuckDB canonical mirror."""

    def __init__(self, org_id: UUID, db: duckdb.DuckDBPyConnection) -> None:
        self.org_id = org_id
        self._db = db

    @classmethod
    async def open(cls, org_id: UUID) -> CanonicalDuckDBWriter:
        db = await asyncio.to_thread(open_duckdb, org_id, read_only=False)
        return cls(org_id, db)

    async def recreate_table(self, qualified_name: str, columns: list[str]) -> None:
        cols_def = ", ".join(f"{quote_ident(column)} VARCHAR" for column in columns)

        def _recreate() -> None:
            quoted = quote_ident(qualified_name)
            self._db.execute(f"DROP TABLE IF EXISTS {quoted}")
            self._db.execute(f"CREATE TABLE {quoted} ({cols_def})")

        await asyncio.to_thread(_recreate)

    async def insert_rows(self, qualified_name: str, rows: list[list[Any]]) -> int:
        if not rows:
            return 0
        placeholders = ", ".join(["?"] * len(rows[0]))

        def _insert() -> None:
            self._db.executemany(
                f"INSERT INTO {quote_ident(qualified_name)} VALUES ({placeholders})",
                rows,
            )

        await asyncio.to_thread(_insert)
        return len(rows)

    async def close(self) -> None:
        await asyncio.to_thread(self._db.close)


def safe_query(
    org_id: UUID, sql: str, *, max_rows: int = 1000,
) -> list[dict[str, Any]]:
    """Run a validated read-only SELECT against an org's canonical DuckDB mirror."""
    if not _SAFE_SQL.match(sql):
        raise ValidationError(
            message="Only SELECT/WITH statements are allowed",
            code="SQL_NOT_SELECT",
            status_hint=400,
        )

    db = open_duckdb(org_id, read_only=True)
    try:
        cur = db.execute(sql)
        rows = cur.fetchmany(max_rows)
        cols = [d[0] for d in cur.description] if cur.description else []
        return [dict(zip(cols, row, strict=True)) for row in rows]
    finally:
        db.close()


def list_canonical_tables(org_id: UUID) -> list[dict[str, Any]]:
    """List all tables present in the org's canonical DuckDB mirror."""
    if not db_path(org_id).exists():
        return []
    db = open_duckdb(org_id, read_only=True)
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
            {"qualified_name": row[0], "column_count": row[1]}
            for row in cur.fetchall()
        ]
    finally:
        db.close()
