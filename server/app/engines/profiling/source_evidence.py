"""Source evidence profiler.

Baseflo should not ship raw customer datasets to LLMs. This module produces
small, deterministic, typed evidence bundles from connector schemas and bounded
sample rows. Specialist agents can use the bundle as facts: value counts,
nullability, distinctness, numeric ranges, currency-column evidence, and
example values capped to a tiny allowance.

The profiler does not decide the final business semantics. It only computes
observations that make later agent decisions cheaper, more private, and more
repeatable.
"""

from __future__ import annotations

from collections import Counter
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from enum import StrEnum
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, ConfigDict, Field

if TYPE_CHECKING:
    from app.connectors.base import SourceSchema


class EvidenceSignal(StrEnum):
    PRIMARY_KEY_DECLARED = "primary_key_declared"
    UNIQUE_IN_SAMPLE = "unique_in_sample"
    LOW_CARDINALITY = "low_cardinality"
    NUMERIC_LIKE = "numeric_like"
    INTEGER_LIKE = "integer_like"
    TEMPORAL_LIKE = "temporal_like"
    EMAIL_LIKE = "email_like"
    ISO_CURRENCY_LIKE = "iso_currency_like"
    MONEY_NAME_HINT = "money_name_hint"


class CurrencyEvidence(BaseModel):
    """Observed currency facts for a source column/table."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    is_currency_code_column: bool = False
    observed_codes: list[str] = Field(default_factory=list, max_length=20)
    uniform_code: str | None = Field(default=None, pattern=r"^[A-Z]{3}$|^$")
    row_coverage: float = Field(default=0.0, ge=0.0, le=1.0)


class ColumnEvidence(BaseModel):
    """Compact facts about one source column."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    connector_name: str = Field(min_length=2, max_length=64)
    table_name: str = Field(min_length=1, max_length=255)
    column_name: str = Field(min_length=1, max_length=255)
    source_type: str = Field(min_length=1, max_length=120)
    nullable: bool
    primary_key_member: bool
    sample_size: int = Field(ge=0)
    non_null_count: int = Field(ge=0)
    null_count: int = Field(ge=0)
    distinct_count: int = Field(ge=0)
    distinct_ratio: float = Field(ge=0.0, le=1.0)
    top_values: list[str] = Field(default_factory=list, max_length=10)
    example_values: list[str] = Field(default_factory=list, max_length=10)
    min_number: float | None = None
    max_number: float | None = None
    numeric_fraction: float = Field(default=0.0, ge=0.0, le=1.0)
    integer_fraction: float = Field(default=0.0, ge=0.0, le=1.0)
    temporal_fraction: float = Field(default=0.0, ge=0.0, le=1.0)
    email_fraction: float = Field(default=0.0, ge=0.0, le=1.0)
    currency: CurrencyEvidence = Field(default_factory=CurrencyEvidence)
    signals: list[EvidenceSignal] = Field(default_factory=list)


class TableEvidence(BaseModel):
    """Compact facts about one source table."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    connector_name: str = Field(min_length=2, max_length=64)
    table_name: str = Field(min_length=1, max_length=255)
    estimated_row_count: int | None = Field(default=None, ge=0)
    sampled_row_count: int = Field(ge=0)
    declared_primary_key: list[str] = Field(default_factory=list)
    candidate_key_columns: list[str] = Field(default_factory=list)
    candidate_currency_columns: list[str] = Field(default_factory=list)
    columns: list[ColumnEvidence] = Field(default_factory=list)


class SourceEvidenceBundle(BaseModel):
    """Profile for one connector's source schema."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    connector_name: str = Field(min_length=2, max_length=64)
    profiled_at: datetime
    tables: list[TableEvidence] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


_COMMON_CURRENCY_CODES: frozenset[str] = frozenset(
    {
        "USD", "EUR", "GBP", "INR", "CAD", "AUD", "NZD", "JPY", "CNY",
        "SGD", "AED", "CHF", "SEK", "NOK", "DKK", "BRL", "MXN", "ZAR",
    }
)

_MONEY_NAME_TOKENS: frozenset[str] = frozenset(
    {
        "amount", "price", "revenue", "sales", "cost", "subtotal", "total",
        "tax", "discount", "fee", "payment", "refund", "charge",
    }
)


def profile_source(
    *,
    connector_name: str,
    schema: SourceSchema,
    rows_by_table: dict[str, list[dict[str, Any]]],
    max_examples: int = 10,
) -> SourceEvidenceBundle:
    """Build a typed evidence bundle for one connector.

    `rows_by_table` should contain bounded samples only. The profiler is
    intentionally pure: same schema + same rows yields the same evidence.
    """

    tables: list[TableEvidence] = []
    notes: list[str] = []
    for table in schema.tables:
        rows = rows_by_table.get(table.name, [])
        columns = [
            _profile_column(
                connector_name=connector_name,
                table_name=table.name,
                column_name=column.name,
                source_type=column.source_type,
                nullable=column.nullable,
                primary_key_member=column.primary_key_member,
                values=[row.get(column.name) for row in rows],
                max_examples=max_examples,
            )
            for column in table.columns
        ]
        candidate_keys = [
            c.column_name for c in columns
            if (
                c.primary_key_member
                or EvidenceSignal.EMAIL_LIKE in c.signals
                or (
                    c.sample_size >= 10
                    and c.non_null_count == c.sample_size
                    and c.distinct_ratio == 1.0
                    and EvidenceSignal.NUMERIC_LIKE not in c.signals
                )
            )
        ]
        currency_columns = [
            c.column_name for c in columns if c.currency.is_currency_code_column
        ]
        tables.append(
            TableEvidence(
                connector_name=connector_name,
                table_name=table.name,
                estimated_row_count=table.estimated_row_count,
                sampled_row_count=len(rows),
                declared_primary_key=list(table.primary_key),
                candidate_key_columns=candidate_keys,
                candidate_currency_columns=currency_columns,
                columns=columns,
            )
        )
        if not rows:
            notes.append(f"{table.name}: no sample rows available.")

    return SourceEvidenceBundle(
        connector_name=connector_name,
        profiled_at=datetime.now(UTC),
        tables=tables,
        notes=notes,
    )


def _profile_column(
    *,
    connector_name: str,
    table_name: str,
    column_name: str,
    source_type: str,
    nullable: bool,
    primary_key_member: bool,
    values: list[Any],
    max_examples: int,
) -> ColumnEvidence:
    sample_size = len(values)
    non_null_values = [v for v in values if v is not None and v != ""]
    non_null_count = len(non_null_values)
    null_count = sample_size - non_null_count

    stringified = [_stringify(v) for v in non_null_values]
    distinct_values = sorted(set(stringified))
    top_values = [value for value, _count in Counter(stringified).most_common(10)]
    examples = _first_unique(stringified, limit=max_examples)

    numbers = [_to_decimal(v) for v in non_null_values]
    number_values = [n for n in numbers if n is not None]
    integer_count = sum(1 for n in number_values if n == n.to_integral_value())

    temporal_count = sum(1 for v in non_null_values if _looks_temporal(v))
    email_count = sum(1 for v in non_null_values if _looks_email(v))
    currency = _currency_evidence(non_null_values)

    signals: list[EvidenceSignal] = []
    if primary_key_member:
        signals.append(EvidenceSignal.PRIMARY_KEY_DECLARED)
    if sample_size > 0 and non_null_count == sample_size and len(distinct_values) == sample_size:
        signals.append(EvidenceSignal.UNIQUE_IN_SAMPLE)
    if 0 < len(distinct_values) <= min(20, max(3, sample_size // 4)):
        signals.append(EvidenceSignal.LOW_CARDINALITY)
    numeric_fraction = _fraction(len(number_values), non_null_count)
    integer_fraction = _fraction(integer_count, non_null_count)
    temporal_fraction = _fraction(temporal_count, non_null_count)
    email_fraction = _fraction(email_count, non_null_count)
    if numeric_fraction >= 0.8:
        signals.append(EvidenceSignal.NUMERIC_LIKE)
    if integer_fraction >= 0.8:
        signals.append(EvidenceSignal.INTEGER_LIKE)
    if temporal_fraction >= 0.8:
        signals.append(EvidenceSignal.TEMPORAL_LIKE)
    if email_fraction >= 0.8:
        signals.append(EvidenceSignal.EMAIL_LIKE)
    if currency.is_currency_code_column:
        signals.append(EvidenceSignal.ISO_CURRENCY_LIKE)
    if _has_money_name_hint(column_name):
        signals.append(EvidenceSignal.MONEY_NAME_HINT)

    return ColumnEvidence(
        connector_name=connector_name,
        table_name=table_name,
        column_name=column_name,
        source_type=source_type,
        nullable=nullable,
        primary_key_member=primary_key_member,
        sample_size=sample_size,
        non_null_count=non_null_count,
        null_count=null_count,
        distinct_count=len(distinct_values),
        distinct_ratio=_fraction(len(distinct_values), non_null_count),
        top_values=top_values,
        example_values=examples,
        min_number=float(min(number_values)) if number_values else None,
        max_number=float(max(number_values)) if number_values else None,
        numeric_fraction=numeric_fraction,
        integer_fraction=integer_fraction,
        temporal_fraction=temporal_fraction,
        email_fraction=email_fraction,
        currency=currency,
        signals=signals,
    )


def _currency_evidence(values: list[Any]) -> CurrencyEvidence:
    string_values = [_stringify(v).upper() for v in values if _stringify(v)]
    if not string_values:
        return CurrencyEvidence()
    codes = sorted({v for v in string_values if v in _COMMON_CURRENCY_CODES})
    matching_codes = sum(1 for v in string_values if v in _COMMON_CURRENCY_CODES)
    coverage = _fraction(matching_codes, len(string_values))
    is_currency_column = coverage >= 0.8 and bool(codes)
    return CurrencyEvidence(
        is_currency_code_column=is_currency_column,
        observed_codes=codes,
        uniform_code=codes[0] if is_currency_column and len(codes) == 1 else None,
        row_coverage=coverage,
    )


def _to_decimal(value: Any) -> Decimal | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int | float | Decimal):
        try:
            return Decimal(str(value))
        except InvalidOperation:
            return None
    if isinstance(value, str):
        text = value.strip().replace(",", "")
        if not text:
            return None
        try:
            return Decimal(text)
        except InvalidOperation:
            return None
    return None


def _looks_temporal(value: Any) -> bool:
    if isinstance(value, datetime):
        return True
    if not isinstance(value, str):
        return False
    text = value.strip()
    if len(text) < 8:
        return False
    try:
        datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return False
    return True


def _looks_email(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    text = value.strip()
    if "@" not in text or "." not in text.rsplit("@", 1)[-1]:
        return False
    return " " not in text and len(text) <= 320


def _has_money_name_hint(column_name: str) -> bool:
    lowered = column_name.lower()
    tokens = lowered.replace("-", "_").split("_")
    return any(token in _MONEY_NAME_TOKENS for token in tokens)


def _first_unique(values: list[str], *, limit: int) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for value in values:
        if value in seen:
            continue
        out.append(value)
        seen.add(value)
        if len(out) >= limit:
            break
    return out


def _stringify(value: Any) -> str:
    if value is None:
        return ""
    return str(value)


def _fraction(numerator: int, denominator: int) -> float:
    if denominator <= 0:
        return 0.0
    return min(1.0, max(0.0, numerator / denominator))
