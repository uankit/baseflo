"""Dynamic catalog builder for Google Sheets.

Per docs/40-features/CONN-SHEETS.md §5. Unlike fixed-model connectors
(Shopify, Stripe), Sheets exposes whatever the user created. The catalog
is built per-spreadsheet from API responses + sampled cells.

Reuses CSV's primitive type-inference helpers — the agent layer's
ColumnClassifier downstream sees a stable "source_type" string regardless
of which connector emitted it.
"""

from __future__ import annotations

import re
from typing import Any

from app.connectors.base import SourceColumn, SourceTable
from app.connectors.csv.parser import infer_source_type
from app.core.errors import BasefloError


__all__ = [
    "build_table_from_grid",
    "sanitize_sheet_title",
    "sheets_from_spreadsheet_response",
]


_NON_IDENTIFIER = re.compile(r"[^a-z0-9_]+")


def sanitize_sheet_title(title: str) -> str:
    """Normalise a Sheets tab title into a snake_case identifier name.

    Mirrors the Excel connector's `sanitize_sheet_name` so cross-source
    reconciliation can match on canonicalised names.
    """
    lower = title.strip().lower().replace(" ", "_").replace("-", "_")
    cleaned = _NON_IDENTIFIER.sub("", lower)
    return cleaned or "sheet"


def sheets_from_spreadsheet_response(payload: dict[str, Any]) -> list[dict[str, Any]]:
    """Extract `sheets[]` from a `GET /v4/spreadsheets/{id}` response.

    Returns the raw list of `properties` blocks (`title`, `sheetId`, `gridProperties`).
    """
    sheets = payload.get("sheets")
    if not isinstance(sheets, list):
        raise BasefloError(
            error_code="BF-CONN-SHEETS-003",
            message="Spreadsheet response missing `sheets` array.",
            status_code=502,
        )
    out: list[dict[str, Any]] = []
    for sheet in sheets:
        if not isinstance(sheet, dict):
            continue
        props = sheet.get("properties")
        if isinstance(props, dict):
            out.append(props)
    return out


def build_table_from_grid(
    *,
    sheet_properties: dict[str, Any],
    grid_values: list[list[Any]],
    has_header: bool,
) -> SourceTable | None:
    """Compose a `SourceTable` from one sheet's properties + a sampled grid.

    `grid_values` is the raw `values` array from `GET /values/{range}`, where
    each row is a list of cell values. Empty grid → returns None (caller skips).
    """
    title = str(sheet_properties.get("title") or "Sheet")
    if not grid_values:
        return None

    if has_header:
        header_row = grid_values[0]
        body = grid_values[1:]
        headers = [
            str(cell).strip() if cell not in (None, "") else f"column_{i + 1}"
            for i, cell in enumerate(header_row)
        ]
    else:
        first_row = grid_values[0]
        headers = [f"column_{i + 1}" for i in range(len(first_row))]
        body = grid_values

    columns: list[SourceColumn] = []
    for col_index, name in enumerate(headers):
        col_values: list[Any] = []
        nullable = False
        for row in body:
            if col_index < len(row):
                v = row[col_index]
                if v in (None, ""):
                    nullable = True
                else:
                    col_values.append(v)
            else:
                nullable = True

        source_type = infer_source_type(col_values)
        columns.append(
            SourceColumn(
                name=name,
                source_type=source_type,
                nullable=nullable,
                sample_values=col_values[:30],
                description=None,
                primary_key_member=False,
            )
        )

    if not columns:
        return None

    grid_props = sheet_properties.get("gridProperties") or {}
    row_count = grid_props.get("rowCount") if isinstance(grid_props, dict) else None
    estimated = (
        max(0, int(row_count) - (1 if has_header else 0))
        if isinstance(row_count, int)
        else None
    )

    return SourceTable(
        name=sanitize_sheet_title(title),
        columns=columns,
        estimated_row_count=estimated,
        primary_key=[],
        description=f"Google Sheets tab: {title!r}",
    )
