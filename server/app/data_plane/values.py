"""Cell normalization for canonical physical storage."""

from __future__ import annotations

import json
from datetime import datetime
from decimal import Decimal
from math import isfinite
from typing import Any


def duckdb_storage_value(value: Any) -> Any:
    """Convert arbitrary connector values into DuckDB VARCHAR-safe cells."""
    if value is None:
        return None
    if isinstance(value, str):
        return value
    if isinstance(value, bool | int):
        return value
    if isinstance(value, float):
        return value if isfinite(value) else None
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, datetime):
        return value.isoformat()
    try:
        return json.dumps(value, default=str, ensure_ascii=False)
    except TypeError:
        return str(value)
