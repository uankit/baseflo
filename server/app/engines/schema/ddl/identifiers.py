"""SQL identifier safety.

The pattern below is the ONLY legitimate semantic-free regex in the codebase
per docs/05-coding-rules.md §1.2. It validates that a candidate identifier
matches Postgres' default rules (snake_case, leading letter, ≤63 chars).
Names that match are emitted bare; names that fail are double-quoted with
internal `"` escaped — this is structural quoting, not semantic classification.
"""

from __future__ import annotations

import re


_IDENTIFIER_RE = re.compile(r"^[a-z][a-z0-9_]{0,62}$")


def is_safe_identifier(name: str) -> bool:
    """True iff `name` is a Postgres-safe bare identifier."""
    return bool(_IDENTIFIER_RE.match(name))


def quote_identifier(name: str) -> str:
    """Return `name` ready for emission. Bare when safe; double-quoted otherwise."""
    if is_safe_identifier(name):
        return name
    escaped = name.replace('"', '""')
    return f'"{escaped}"'


def quote_string_literal(value: str) -> str:
    """Postgres single-quoted string literal with internal `'` doubled."""
    return "'" + value.replace("'", "''") + "'"
