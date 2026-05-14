from __future__ import annotations

import io
import re
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from math import isfinite
from typing import Any


_SLUG_RE = re.compile(r"[^a-z0-9]+")


class SpreadsheetPreprocessorUnavailable(Exception):
    """Raised when a required spreadsheet parser dependency is missing."""


@dataclass(frozen=True, slots=True)
class PreprocessedTable:
    name: str
    label: str
    sheet_name: str
    columns: list[str]
    rows: list[list[Any]]
    source: str = "canonical_grid"
    metadata: dict[str, Any] = field(default_factory=dict)


def slug(value: str) -> str:
    text = _SLUG_RE.sub("_", value.lower()).strip("_")
    return text or "sheet"


def _json_safe_cell(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, str):
        text = value.strip()
        return text or None
    if isinstance(value, datetime | date | time):
        return value.isoformat()
    if isinstance(value, timedelta):
        return value.total_seconds()
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, bool | int):
        return value
    if isinstance(value, float):
        return value if isfinite(value) else None
    text = str(value).strip()
    return text or None


def _row_width(values: list[list[Any]]) -> int:
    return max((len(row) for row in values), default=0)


def _has_any_value(values: list[list[Any]]) -> bool:
    return any(_json_safe_cell(cell) is not None for row in values for cell in row)


def _canonical_columns(width: int) -> list[str]:
    return ["row_number", *[f"column_{idx + 1}" for idx in range(width)]]


def _canonical_row(row_number: int, row: list[Any], width: int) -> list[Any]:
    cells = [
        _json_safe_cell(row[idx] if idx < len(row) else None)
        for idx in range(width)
    ]
    return [row_number, *cells]


def preview_rows(
    table: PreprocessedTable,
    *,
    limit: int = 25,
    max_columns: int = 30,
) -> list[dict[str, Any]]:
    columns = table.columns[:max_columns]
    return [
        {
            column: row[idx] if idx < len(row) else None
            for idx, column in enumerate(columns)
        }
        for row in table.rows[:limit]
    ]


def preprocess_grid(
    sheet_name: str,
    values: list[list[Any]],
    *,
    source: str = "canonical_grid",
    metadata: dict[str, Any] | None = None,
) -> list[PreprocessedTable]:
    """Convert a worksheet into Baseflo's raw canonical grid format.

    This deliberately does not infer headers, remove title rows, collapse blank
    rows, split subtables, or rename business columns. A sheet tab becomes one
    rectangular table: `row_number`, then `column_1..column_n`.
    """
    width = _row_width(values)
    if width == 0 or not _has_any_value(values):
        return []

    rows = [
        _canonical_row(row_number, row, width)
        for row_number, row in enumerate(values, start=1)
    ]
    table_metadata = {
        "format": "canonical_grid_v1",
        "sheet_name": sheet_name,
        "grid_width": width,
        "grid_height": len(values),
        **(metadata or {}),
    }
    return [
        PreprocessedTable(
            name=slug(sheet_name),
            label=sheet_name,
            sheet_name=sheet_name,
            columns=_canonical_columns(width),
            rows=rows,
            source=source,
            metadata=table_metadata,
        )
    ]


def preprocess_xlsx_bytes(
    file_bytes: bytes,
    *,
    filename: str | None = None,
) -> list[PreprocessedTable]:
    """Convert every XLSX tab into Baseflo's raw canonical grid format."""
    try:
        from openpyxl import load_workbook
    except Exception as exc:  # pragma: no cover - exercised when dependency is absent.
        raise SpreadsheetPreprocessorUnavailable(str(exc)) from exc

    workbook = load_workbook(
        io.BytesIO(file_bytes),
        read_only=True,
        data_only=True,
    )
    tables: list[PreprocessedTable] = []
    for worksheet in workbook.worksheets:
        values = [
            list(row)
            for row in worksheet.iter_rows(
                min_row=1,
                max_row=worksheet.max_row,
                min_col=1,
                max_col=worksheet.max_column,
                values_only=True,
            )
        ]
        tables.extend(
            preprocess_grid(
                worksheet.title,
                values,
                source="openpyxl_canonical_grid",
                metadata={"filename": filename},
            )
        )
    return tables
