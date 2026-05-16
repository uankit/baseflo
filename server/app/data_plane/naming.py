"""Source-neutral naming rules for canonical storage."""

from __future__ import annotations

import re
from typing import Any

from app.data_plane.contracts import CANONICAL_META_COLUMNS

_SLUG_RE = re.compile(r"[^a-z0-9]+")


def slug(name: str) -> str:
    value = _SLUG_RE.sub("_", name.lower()).strip("_")
    return value or "untitled"


def qualified_name(source_name: str, asset_name: str) -> str:
    """Deterministic DuckDB table name for a source asset."""
    return f"{slug(source_name)}__{slug(asset_name)}"


def quote_ident(value: str) -> str:
    return '"' + value.replace('"', '""') + '"'


def clean_column_name(value: Any, index: int) -> str:
    text = str(value).strip() if value is not None else ""
    return text or f"column_{index + 1}"


def unique_column_names(values: list[Any]) -> list[str]:
    names: list[str] = []
    seen: dict[str, int] = {}
    for index, value in enumerate(values):
        base = clean_column_name(value, index)
        count = seen.get(base, 0) + 1
        seen[base] = count
        names.append(base if count == 1 else f"{base}_{count}")
    return names


def canonical_storage_columns(
    source_columns: list[str],
) -> tuple[list[str], dict[str, str | None]]:
    """Return physical DuckDB columns plus a storage->source lineage map."""
    columns = list(CANONICAL_META_COLUMNS)
    source_by_storage: dict[str, str | None] = dict.fromkeys(CANONICAL_META_COLUMNS)
    seen = set(columns)
    for source_column in source_columns:
        base = source_column
        if base in seen or base.startswith("_bf_"):
            base = f"source_{base}"
        storage = base
        suffix = 2
        while storage in seen:
            storage = f"{base}_{suffix}"
            suffix += 1
        seen.add(storage)
        columns.append(storage)
        source_by_storage[storage] = source_column
    return columns, source_by_storage
