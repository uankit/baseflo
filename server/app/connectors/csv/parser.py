"""CSV parsing + deterministic header detection + type inference.

Per docs/40-features/CONN-CSV.md §5 + §10. The header decision is the only
non-trivial classification this module makes; per the canonical spec the
user can pin it explicitly via the connector's auth payload, and the
auto-detector is a deterministic structural algorithm — never a heuristic.

Algorithm: per-column TYPE-DISAGREEMENT.

  Each cell is classified as PRIMITIVE (parses as int/float/bool/date/datetime)
  or LABEL (anything else, including empty). For each column the first row's
  classification is compared against the rest:

    row 0 = LABEL,     rows 1+ predominantly PRIMITIVE  → +1 header_evidence
    row 0 = PRIMITIVE, every row 1+ also PRIMITIVE      → +1 no_header_evidence
    otherwise                                            → no signal

  HEADER_PRESENT iff header_evidence > 0 and no_header_evidence == 0.
  NO_HEADER       iff no_header_evidence > 0 and header_evidence == 0.
  AMBIGUOUS       in every other case — including pure-text tables, single-row
                  inputs, and contradictory column signals. AMBIGUOUS surfaces
                  to the user via BF-CONN-CSV-005 so they pin `has_header`.

Per docs/05-coding-rules.md §5.3 (no silent fallbacks): an unparseable
dialect raises BF-CONN-CSV-006 instead of pretending it's a comma file.
"""

from __future__ import annotations

import csv
from collections.abc import Iterable
from datetime import date, datetime
from enum import StrEnum
from io import StringIO
from typing import Any

from app.core.errors import BasefloError


__all__ = [
    "HeaderDecision",
    "detect_dialect",
    "detect_header",
    "infer_source_type",
    "parse_text",
]


_TRUE_LITERALS = frozenset({"true", "yes", "y", "t", "1"})
_FALSE_LITERALS = frozenset({"false", "no", "n", "f", "0"})


# ---------- Dialect ----------


_CANDIDATE_DELIMITERS: tuple[str, ...] = (",", "\t", ";", "|")


def detect_dialect(sample: str) -> type[csv.Dialect]:
    """Detect the CSV dialect deterministically from a sample.

    Algorithm: count candidate delimiters (``, \\t ; |``) in the FIRST non-empty
    line. The unique highest-count delimiter wins. Outcomes:

      - exactly one winner (count > 0)  → custom dialect with that delimiter
      - all counts zero                 → single-column file → ``csv.excel``
      - tie for the top count           → genuinely undecidable → BF-CONN-CSV-006

    This avoids `csv.Sniffer`'s requirement that every row have the same column
    count, which trips on ragged rows that real spreadsheets routinely emit.
    Per docs/05-coding-rules.md §5.3, the tie case raises rather than guessing.
    """
    first_line = _first_non_empty_line(sample)
    if not first_line:
        return csv.excel

    counts = {d: first_line.count(d) for d in _CANDIDATE_DELIMITERS}
    max_count = max(counts.values())
    if max_count == 0:
        # Single-column file: no delimiter present anywhere on row 0.
        return csv.excel

    winners = [d for d, c in counts.items() if c == max_count]
    if len(winners) > 1:
        raise BasefloError(
            error_code="BF-CONN-CSV-006",
            message=(
                "Could not determine CSV delimiter: "
                f"candidates {winners!r} occur equally often on the first line. "
                "Re-upload with the file's delimiter explicit."
            ),
            status_code=400,
        )

    return _dialect_with_delimiter(winners[0])


def _first_non_empty_line(sample: str) -> str:
    for line in sample.splitlines():
        if line.strip():
            return line
    return ""


def _dialect_with_delimiter(delimiter: str) -> type[csv.Dialect]:
    """Build a `csv.Dialect` subclass whose only override is `delimiter`.

    All other fields inherit Excel-canonical defaults (quotechar=``"``,
    doublequote=True, QUOTE_MINIMAL). New class per call so callers can
    introspect `.delimiter` without singleton mutation risk.
    """
    class _Dialect(csv.excel):
        pass

    _Dialect.delimiter = delimiter
    return _Dialect


# ---------- Header detection ----------


class HeaderDecision(StrEnum):
    """Outcome of the deterministic header detector."""

    HEADER_PRESENT = "header_present"
    NO_HEADER = "no_header"
    AMBIGUOUS = "ambiguous"


def detect_header(rows: list[list[str]]) -> HeaderDecision:
    """Decide whether `rows[0]` is a header by comparing column type signatures.

    Pure function. Same input → same output. See module docstring for the
    algorithm.
    """
    if len(rows) < 2:
        return HeaderDecision.AMBIGUOUS

    first = rows[0]
    rest = rows[1:]
    n_cols = len(first)

    header_evidence = 0
    no_header_evidence = 0

    for i in range(n_cols):
        first_cell = first[i] if i < len(first) else ""
        first_kind = _classify_cell(first_cell)

        rest_kinds = [
            _classify_cell(r[i] if i < len(r) else "") for r in rest
        ]
        if not rest_kinds:
            continue

        rest_primitive = sum(1 for k in rest_kinds if k == _Kind.PRIMITIVE)
        rest_label = len(rest_kinds) - rest_primitive

        if first_kind == _Kind.LABEL and rest_primitive > rest_label:
            header_evidence += 1
        elif first_kind == _Kind.PRIMITIVE and rest_primitive == len(rest_kinds):
            no_header_evidence += 1
        # else: column is uninformative (label/label or contradictory).

    if header_evidence > 0 and no_header_evidence == 0:
        return HeaderDecision.HEADER_PRESENT
    if no_header_evidence > 0 and header_evidence == 0:
        return HeaderDecision.NO_HEADER
    return HeaderDecision.AMBIGUOUS


class _Kind(StrEnum):
    PRIMITIVE = "primitive"
    LABEL = "label"


def _classify_cell(cell: str) -> _Kind:
    """A cell is PRIMITIVE iff it parses as one of our typed primitives.

    Empty / whitespace cells classify as LABEL — neutral; if every column
    in row 0 is empty the row carries no header signal and detection falls
    through to AMBIGUOUS.
    """
    if not isinstance(cell, str):
        return _Kind.LABEL
    stripped = cell.strip()
    if not stripped:
        return _Kind.LABEL
    if (
        _try_int(stripped) is not None
        or _try_float(stripped) is not None
        or _try_bool(stripped) is not None
        or _try_iso_date(stripped) is not None
        or _try_iso_datetime(stripped) is not None
    ):
        return _Kind.PRIMITIVE
    return _Kind.LABEL


# ---------- Top-level parse ----------


def parse_text(
    text: str,
    *,
    has_header: bool | None = None,
    max_rows: int | None = None,
) -> tuple[list[str], list[dict[str, Any]]]:
    """Parse CSV text into `(headers, rows)`.

    Args:
        text: full CSV body. Empty string → ``([], [])``.
        has_header: explicit override.
            - ``True``  — first row is the header.
            - ``False`` — synthesize ``column_1..N`` headers; first row is data.
            - ``None``  — auto-detect via `detect_header`. AMBIGUOUS raises
              `BF-CONN-CSV-005`; the caller (CSVConnector) surfaces this so
              the user can re-upload with an explicit flag.
        max_rows: cap on data rows returned. None = unbounded.
    """
    if not text.strip():
        return [], []

    sample = text[:8192]
    dialect = detect_dialect(sample)

    all_rows = list(csv.reader(StringIO(text), dialect=dialect))
    if not all_rows:
        return [], []

    resolved_has_header = _resolve_has_header(all_rows, has_header)

    if resolved_has_header:
        headers = [h.strip() for h in all_rows[0]]
        data_rows = all_rows[1:]
    else:
        first = all_rows[0]
        headers = [f"column_{i + 1}" for i in range(len(first))]
        data_rows = all_rows

    if max_rows is not None:
        data_rows = data_rows[:max_rows]

    rows = [_zip_row(headers, row) for row in data_rows]
    return headers, rows


def _resolve_has_header(rows: list[list[str]], explicit: bool | None) -> bool:
    if explicit is not None:
        return explicit
    decision = detect_header(rows)
    if decision == HeaderDecision.HEADER_PRESENT:
        return True
    if decision == HeaderDecision.NO_HEADER:
        return False
    raise BasefloError(
        error_code="BF-CONN-CSV-005",
        message=(
            "Could not determine whether the first row is a header. "
            "Re-upload with an explicit `has_header` flag (true / false)."
        ),
        status_code=400,
    )


def _zip_row(headers: list[str], values: list[str]) -> dict[str, Any]:
    """Pair headers with values, padding short rows with None and dropping
    extra cells (the agent layer surfaces structural mismatches via warnings)."""
    out: dict[str, Any] = {}
    for i, header in enumerate(headers):
        if i < len(values):
            cell = values[i]
            v = cell.strip() if isinstance(cell, str) else cell
            out[header] = None if v == "" else v
        else:
            out[header] = None
    return out


# ---------- Type-primitive parsers ----------


def _try_int(s: str) -> int | None:
    try:
        return int(s)
    except (TypeError, ValueError):
        return None


def _try_float(s: str) -> float | None:
    try:
        return float(s)
    except (TypeError, ValueError):
        return None


def _try_bool(s: str) -> bool | None:
    if not isinstance(s, str):
        return None
    norm = s.strip().lower()
    if norm in _TRUE_LITERALS:
        return True
    if norm in _FALSE_LITERALS:
        return False
    return None


def _try_iso_datetime(s: str) -> datetime | None:
    """Parse ISO datetime — but ONLY when the string actually carries a time.

    Python's `datetime.fromisoformat("2026-05-07")` accepts pure dates and
    returns a midnight datetime. That hides the date type. Require a time
    marker (`T` / space / `:`) so pure dates fall through to `_try_iso_date`.
    """
    if not isinstance(s, str):
        return None
    if "T" not in s and " " not in s.strip() and ":" not in s:
        return None
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None


def _try_iso_date(s: str) -> date | None:
    try:
        return date.fromisoformat(s)
    except (TypeError, ValueError):
        return None


def infer_source_type(values: Iterable[Any]) -> str:
    """Walk values once and emit a connector-native type string.

    Order of preference: integer > float > boolean > date > datetime > string.
    Date precedes datetime so a pure-date string like ``"2026-05-07"`` is
    classified as ``"date"`` rather than promoted to ``"datetime"``.
    """
    non_null = [v for v in values if v is not None and v != ""]
    if not non_null:
        return "string"

    if all(_try_int(str(v)) is not None for v in non_null):
        return "integer"

    if all(_try_float(str(v)) is not None for v in non_null):
        return "number"

    if all(_try_bool(str(v)) is not None for v in non_null):
        return "boolean"

    if all(_try_iso_date(str(v)) is not None for v in non_null):
        return "date"

    if all(_try_iso_datetime(str(v)) is not None for v in non_null):
        return "datetime"

    return "string"
