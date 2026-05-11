"""CanonicalRowReader — stream rows from a project's tenant schema into the export.

Per docs/40-features/SECURITY.md §3.5. The export composer accepts a
`rows_by_table` mapping; this reader fills it by streaming from the
per-tenant Postgres schema that `SchemaApplier` provisioned.

The reader uses `text("SELECT ...")` with a stable column order derived from
the IR (so the CSV header columns match the IR-defined column set, not
whatever order Postgres returns). Schema + table names are validated as
identifiers before interpolation.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import BasefloError
from app.engines.schema.ddl.identifiers import is_safe_identifier, quote_identifier
from app.engines.schema.ir import SchemaIR


__all__ = ["CanonicalRowReader"]


class CanonicalRowReader:
    """Reads rows from `<schema>.<table>` for a finalized SchemaIR."""

    def __init__(self, *, session: AsyncSession, schema_name: str) -> None:
        if not is_safe_identifier(schema_name):
            raise BasefloError(
                error_code="BF-DATAPLANE-002",
                message=f"Unsafe schema name: {schema_name!r}.",
                status_code=500,
            )
        self._session = session
        self._schema_name = schema_name

    async def iter_table_rows(
        self, *, table_name: str, columns: list[str], batch_size: int = 1000,
    ) -> AsyncIterator[dict[str, Any]]:
        """Async-stream rows from one table.

        `columns` is the IR-declared column order. The reader runs `SELECT
        <cols> FROM <schema>.<table>` and yields each row as a `dict[col, val]`.
        """
        if not is_safe_identifier(table_name):
            raise BasefloError(
                error_code="BF-DATAPLANE-004",
                message=f"Unsafe table name: {table_name!r}.",
                status_code=500,
            )
        for col in columns:
            if not is_safe_identifier(col):
                raise BasefloError(
                    error_code="BF-DATAPLANE-004",
                    message=f"Unsafe column name: {col!r}.",
                    status_code=500,
                )

        column_clause = ", ".join(quote_identifier(c) for c in columns)
        sql = (
            f"SELECT {column_clause} "
            f"FROM {quote_identifier(self._schema_name)}."
            f"{quote_identifier(table_name)} "
            f"ORDER BY {quote_identifier(columns[0]) if columns else 'id'}"
        )
        # `execution_options(stream_results=True)` plus a yield_per gives us
        # async server-side streaming; rows arrive in `batch_size`-chunks.
        result = await self._session.stream(
            text(sql).execution_options(stream_results=True, yield_per=batch_size),
        )
        async for row in result.mappings():
            yield dict(row)

    async def collect_rows_by_table(
        self, *, ir: SchemaIR, batch_size: int = 1000,
    ) -> dict[str, list[dict[str, Any]]]:
        """Convenience: read all rows for every IR table into a dict.

        Returns a fully-materialised mapping; callers that need streaming
        for large exports should iterate `iter_table_rows` table-by-table
        and feed the export composer directly.
        """
        rows_by_table: dict[str, list[dict[str, Any]]] = {}
        for table in ir.tables:
            column_names = [c.name for c in table.columns]
            rows: list[dict[str, Any]] = []
            async for row in self.iter_table_rows(
                table_name=table.name,
                columns=column_names,
                batch_size=batch_size,
            ):
                rows.append(row)
            rows_by_table[table.name] = rows
        return rows_by_table
