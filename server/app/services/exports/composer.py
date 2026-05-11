"""Compose a project's full data export into a tarball.

Per docs/30-features.md SEC-EXPORT. The archive's manifest:

  baseflo-export-<project-slug>-<version>.tar.gz
  ├── README.md                 # what's inside + how to re-import
  ├── ir.json                   # the unified SchemaIR
  ├── kpi_definitions.json
  ├── tables/<table>.csv        # one CSV per reconciled table
  └── ddl.sql                   # CREATE TABLE statements (Postgres dialect)

The composer is pure: given the IR + per-table row iterables, it produces
a single bytes blob. Persistence (S3 / signed URLs) lives one layer up.
"""

from __future__ import annotations

import csv
import io
import json
import tarfile
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from app.engines.schema.ddl.compiler import compile_ir
from app.engines.schema.ir import SchemaIR


__all__ = [
    "ExportArchive",
    "ExportComposer",
    "compose_export_archive",
]


@dataclass(frozen=True, slots=True)
class ExportArchive:
    """Result of composing one export."""

    bytes_: bytes
    filename: str
    table_count: int
    row_count: int
    composed_at: datetime


def compose_export_archive(
    *,
    project_slug: str,
    project_version_id: UUID,
    schema_ir: SchemaIR,
    kpi_definitions: list[dict[str, Any]] | None = None,
    rows_by_table: Mapping[str, Iterable[dict[str, Any]]] | None = None,
) -> ExportArchive:
    """Build the tarball for a project version.

    `rows_by_table` is optional — empty when the project has no rows yet
    (description-only flow). When present, each table gets a CSV with its
    canonical columns + every supplied row.
    """
    composed = ExportComposer().build(
        project_slug=project_slug,
        project_version_id=project_version_id,
        schema_ir=schema_ir,
        kpi_definitions=kpi_definitions or [],
        rows_by_table=rows_by_table or {},
    )
    return composed


class ExportComposer:
    """Stateless builder. Same input → byte-identical archive (modulo time)."""

    def build(
        self,
        *,
        project_slug: str,
        project_version_id: UUID,
        schema_ir: SchemaIR,
        kpi_definitions: list[dict[str, Any]],
        rows_by_table: Mapping[str, Iterable[dict[str, Any]]],
    ) -> ExportArchive:
        composed_at = datetime.now(UTC)
        buffer = io.BytesIO()
        row_count = 0
        with tarfile.open(fileobj=buffer, mode="w:gz") as tar:
            self._add_text(tar, "README.md", _README.format(
                project_slug=project_slug,
                project_version_id=project_version_id,
                composed_at=composed_at.isoformat(),
                table_count=len(schema_ir.tables),
            ))
            self._add_text(tar, "ir.json", json.dumps(
                schema_ir.model_dump(mode="json"), sort_keys=True, indent=2,
            ))
            self._add_text(tar, "kpi_definitions.json", json.dumps(
                kpi_definitions, sort_keys=True, indent=2,
            ))
            ddl_result = compile_ir(schema_ir)
            self._add_text(tar, "ddl.sql", ddl_result.sql)
            self._add_text(tar, ".env.example", _ENV_EXAMPLE)

            for table in schema_ir.tables:
                csv_bytes, table_row_count = self._table_to_csv(
                    table_name=table.name,
                    column_names=[c.name for c in table.columns],
                    rows=rows_by_table.get(table.name, []),
                )
                self._add_bytes(tar, f"tables/{table.name}.csv", csv_bytes)
                row_count += table_row_count

        filename = (
            f"baseflo-export-{project_slug}-{project_version_id}.tar.gz"
        )
        return ExportArchive(
            bytes_=buffer.getvalue(),
            filename=filename,
            table_count=len(schema_ir.tables),
            row_count=row_count,
            composed_at=composed_at,
        )

    # ---------- internal ----------

    def _table_to_csv(
        self,
        *,
        table_name: str,
        column_names: list[str],
        rows: Iterable[dict[str, Any]],
    ) -> tuple[bytes, int]:
        _ = table_name
        out = io.StringIO()
        writer = csv.DictWriter(
            out, fieldnames=column_names, extrasaction="ignore",
            lineterminator="\n",
        )
        writer.writeheader()
        count = 0
        for row in rows:
            writer.writerow({c: _serialise_cell(row.get(c)) for c in column_names})
            count += 1
        return out.getvalue().encode("utf-8"), count

    def _add_text(self, tar: tarfile.TarFile, path: str, text: str) -> None:
        self._add_bytes(tar, path, text.encode("utf-8"))

    def _add_bytes(self, tar: tarfile.TarFile, path: str, payload: bytes) -> None:
        info = tarfile.TarInfo(name=path)
        info.size = len(payload)
        info.mtime = 0  # deterministic; archive bytes don't depend on system clock
        tar.addfile(info, io.BytesIO(payload))


def _serialise_cell(value: Any) -> str:
    """CSV-friendly string for a Python cell value.

    Datetimes → ISO 8601; lists/dicts → JSON; None → empty cell;
    everything else → str(value).
    """
    if value is None:
        return ""
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, (list, dict)):
        return json.dumps(value, sort_keys=True)
    return str(value)


_README = """\
# Baseflo Export

Project: `{project_slug}`
Version: `{project_version_id}`
Generated: `{composed_at}`
Tables: {table_count}

This archive is the full, take-everything-and-leave export of your project.

## Contents

- `ir.json` — the unified SchemaIR (canonical schema definition).
- `kpi_definitions.json` — KPIs the agent layer planned for this project.
- `ddl.sql` — Postgres `CREATE TABLE` statements derived from the IR.
- `tables/<name>.csv` — one CSV per reconciled table with the canonical
  column set (UTF-8, comma-delimited, header row included).
- `.env.example` — environment-variable template for re-importing.

## Re-importing

```sh
createdb baseflo_imported
psql baseflo_imported -f ddl.sql
for f in tables/*.csv; do
  table=$(basename "$f" .csv)
  psql baseflo_imported -c "\\COPY \"$table\" FROM '$f' WITH CSV HEADER"
done
```

Your data is portable; Baseflo is not lock-in.
"""

_ENV_EXAMPLE = """\
# Re-import target. Point this at any Postgres 15+ instance you control.
DATABASE_URL=postgresql://user:password@localhost:5432/baseflo_imported
"""
