"""Excel `.xlsx` parsing — workbook → list[SourceTable] + sheet row iteration.

Per docs/40-features/CONN-EXCEL.md. Uses openpyxl for the binary parse;
falls back to CSV's primitive-type inference for cells openpyxl reports
as plain strings.

Pure-ish: opens the workbook, walks it, returns typed values. No connector
state, no token vault interaction.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import date, datetime
from pathlib import Path
from typing import Any

import openpyxl

from app.connectors.base import SourceColumn, SourceTable
from app.connectors.csv.parser import (
    _try_bool,
    _try_float,
    _try_int,
    _try_iso_date,
    _try_iso_datetime,
)
from app.core.errors import BasefloError


__all__ = [
    "MAX_SHEETS",
    "MAX_TYPE_INFERENCE_ROWS",
    "introspect_workbook",
    "iter_sheet_rows",
    "sanitize_sheet_name",
]


MAX_SHEETS = 50
"""Per CONN-EXCEL.md §9 BF-CONN-EXCEL-003. Workbooks beyond this cap are
treated as malformed input — usually a sign the user uploaded a metadata-
exported file rather than a data sheet."""

MAX_TYPE_INFERENCE_ROWS = 1000
"""Cap on cells per column that we sample for type inference. Bigger sheets
are common; we don't need every cell to make a typing decision."""


def sanitize_sheet_name(name: str) -> str:
    """Map a sheet's display name to a snake_case identifier-safe table name.

    Same shape as CSV's table_name derivation: lower-case, spaces → `_`,
    keep `[a-z0-9_]`, drop everything else.
    """
    lower = name.strip().lower().replace(" ", "_").replace("-", "_")
    cleaned = "".join(ch for ch in lower if ch.isalnum() or ch == "_")
    return cleaned or "sheet"


def introspect_workbook(
    path: Path, *, has_header: bool | None = None
) -> list[SourceTable]:
    """Open `path` and emit one `SourceTable` per non-empty sheet.

    `has_header`:
      - None  → default True (matches CSV connector's auto-detect-positive bias)
      - True  → first row is the header
      - False → synthesize `column_1..N` headers; first row is data
    """
    workbook = _open_workbook(path)
    try:
        sheet_names = workbook.sheetnames
        if len(sheet_names) > MAX_SHEETS:
            raise BasefloError(
                error_code="BF-CONN-EXCEL-003",
                message=(
                    f"Workbook has {len(sheet_names)} sheets; the connector caps at "
                    f"{MAX_SHEETS}. Split into multiple uploads."
                ),
                status_code=400,
            )

        tables: list[SourceTable] = []
        for sheet_name in sheet_names:
            ws = workbook[sheet_name]
            if ws.max_row is None or ws.max_row == 0:
                continue
            if ws.max_column is None or ws.max_column == 0:
                continue

            table = _introspect_sheet(
                worksheet=ws, sheet_name=sheet_name, has_header=has_header,
            )
            if table is not None:
                tables.append(table)
        return tables
    finally:
        workbook.close()


def iter_sheet_rows(
    path: Path,
    *,
    sheet_table_name: str,
    has_header: bool | None,
    max_rows: int | None,
) -> Iterator[dict[str, Any]]:
    """Stream rows from one sheet as `dict[header, value]`.

    Caller resolves `sheet_table_name` from the catalog the same way the
    connector does. Header presence follows `has_header` exactly the same way
    `introspect_workbook` does. Generator closes the workbook on exhaustion
    or external `.close()`.
    """
    workbook = _open_workbook(path, read_only=True)
    try:
        target_ws = None
        for name in workbook.sheetnames:
            if sanitize_sheet_name(name) == sheet_table_name:
                target_ws = workbook[name]
                break
        if target_ws is None:
            raise BasefloError(
                error_code="BF-CONN-EXCEL-004",
                message=f"Workbook does not contain a sheet matching {sheet_table_name!r}.",
                status_code=400,
            )

        rows_iter = target_ws.iter_rows(values_only=True)
        try:
            first = next(rows_iter)
        except StopIteration:
            return

        resolved_header = True if has_header is None else has_header
        if resolved_header:
            headers = [_header_cell_to_str(c, i) for i, c in enumerate(first)]
        else:
            headers = [f"column_{i + 1}" for i in range(len(first))]
            yield _zip_row(headers, first)

        emitted = 0
        for raw_row in rows_iter:
            if max_rows is not None and emitted >= max_rows:
                return
            yield _zip_row(headers, raw_row)
            emitted += 1
    finally:
        workbook.close()


# ---------- internal ----------


def _open_workbook(path: Path, *, read_only: bool = False) -> openpyxl.Workbook:
    if not path.is_file():
        raise BasefloError(
            error_code="BF-CONN-EXCEL-001",
            message=f"Excel file not found at path: {path}",
            status_code=400,
        )
    try:
        return openpyxl.load_workbook(
            filename=str(path), read_only=read_only, data_only=True
        )
    except Exception as exc:  # noqa: BLE001 — openpyxl raises a zoo of exceptions
        raise BasefloError(
            error_code="BF-CONN-EXCEL-001",
            message=f"Failed to open Excel workbook at {path}: {exc!r}",
            status_code=400,
            cause=exc,
        ) from exc


def _introspect_sheet(
    *, worksheet: Any, sheet_name: str, has_header: bool | None
) -> SourceTable | None:
    rows_iter = worksheet.iter_rows(values_only=False)
    try:
        first_row_cells = next(rows_iter)
    except StopIteration:
        return None

    resolved_header = True if has_header is None else has_header
    if resolved_header:
        if not _is_label_row(first_row_cells):
            raise BasefloError(
                error_code="BF-CONN-EXCEL-002",
                message=(
                    f"Sheet {sheet_name!r}: first row looks like data (typed cells). "
                    "Re-upload with `has_header=false` if the sheet has no header row."
                ),
                status_code=400,
            )
        headers = [_header_cell_to_str(c.value, i) for i, c in enumerate(first_row_cells)]
        body_iter: Iterator[tuple[Any, ...]] = rows_iter
    else:
        # First row is data; synthesize column_N headers.
        headers = [f"column_{i + 1}" for i in range(len(first_row_cells))]

        def _replay() -> Iterator[tuple[Any, ...]]:
            yield first_row_cells
            yield from rows_iter

        body_iter = _replay()

    column_samples: list[list[Any]] = [[] for _ in headers]
    nullable_flags: list[bool] = [False for _ in headers]
    inferred_kinds: list[str] = ["string" for _ in headers]

    sampled_rows = 0
    for cells in body_iter:
        if sampled_rows >= MAX_TYPE_INFERENCE_ROWS:
            break
        for col_index, cell in enumerate(cells):
            if col_index >= len(headers):
                break
            value = cell.value
            if value is None:
                nullable_flags[col_index] = True
                continue
            if len(column_samples[col_index]) < 30:
                column_samples[col_index].append(value)
            inferred_kinds[col_index] = _refine_kind(inferred_kinds[col_index], value)
        sampled_rows += 1

    columns = [
        SourceColumn(
            name=name,
            source_type=inferred_kinds[i],
            nullable=nullable_flags[i],
            sample_values=column_samples[i],
            description=None,
            primary_key_member=False,
        )
        for i, name in enumerate(headers)
    ]
    return SourceTable(
        name=sanitize_sheet_name(sheet_name),
        columns=columns,
        estimated_row_count=worksheet.max_row - (1 if resolved_header else 0),
        primary_key=[],
        description=f"Excel sheet: {sheet_name!r}",
    )


def _refine_kind(current: str, value: Any) -> str:
    """Refine a column's inferred kind by one cell's value.

    Order matters: `bool` must come before `int` (bool IS-A int in Python),
    `float` before `int` so a column with `12.5` and `1` resolves to
    `"number"` not `"integer"`. Strings dispatch to the CSV primitive
    helpers so date-shaped strings get classified properly.
    """
    if isinstance(value, datetime):
        return "datetime"
    if isinstance(value, date):
        return "date"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, float):
        if current in {"string", "integer"}:
            return "number"
        return current
    if isinstance(value, int):
        if current == "string":
            return "integer"
        return current

    text = str(value)
    if current == "string":
        if _try_int(text) is not None:
            return "integer"
        if _try_float(text) is not None:
            return "number"
        if _try_bool(text) is not None:
            return "boolean"
        if _try_iso_date(text) is not None:
            return "date"
        if _try_iso_datetime(text) is not None:
            return "datetime"
    return current


def _is_label_row(cells: tuple[Any, ...]) -> bool:
    """True iff at least one cell looks like a header label (non-empty,
    not parseable as a primitive). Mirrors CSV's deterministic detector."""
    saw_label = False
    for cell in cells:
        value = cell.value
        if value is None:
            continue
        if isinstance(value, (int, float, bool, datetime, date)):
            return False  # typed value present → looks like data
        text = str(value).strip()
        if not text:
            continue
        if (
            _try_int(text) is not None
            or _try_float(text) is not None
            or _try_bool(text) is not None
            or _try_iso_date(text) is not None
            or _try_iso_datetime(text) is not None
        ):
            return False
        saw_label = True
    return saw_label


def _header_cell_to_str(value: Any, index: int) -> str:
    """Coerce a header-row cell value into a column-name string. Empty cells
    fall back to `column_<index>` so the SourceColumn schema's `name` is
    always non-empty."""
    if value is None:
        return f"column_{index + 1}"
    return str(value).strip() or f"column_{index + 1}"


def _zip_row(headers: list[str], values: tuple[Any, ...] | list[Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for i, header in enumerate(headers):
        if i < len(values):
            v = values[i]
            out[header] = None if v == "" else v
        else:
            out[header] = None
    return out
