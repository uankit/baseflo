"""Pure deterministic inference helpers for field profiling."""

from __future__ import annotations

import json
import math
import re
from collections import Counter
from datetime import datetime
from typing import Any

from app.data_profiler.contracts import (
    FieldCandidate,
    FieldProfile,
    ObservedType,
    ParseProfile,
)

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_URL_RE = re.compile(r"^https?://", re.IGNORECASE)
_MONEY_RE = re.compile(r"^\s*[$₹€£]?\s*-?\d[\d,]*(?:\.\d+)?\s*$")
_ID_HINTS = ("id", "uuid", "gid", "key", "code")
_LABEL_HINTS = ("name", "title", "email", "phone", "sku", "party", "customer", "vendor")
_MEASURE_HINTS = (
    "amount",
    "amt",
    "total",
    "price",
    "qty",
    "quantity",
    "count",
    "spend",
    "revenue",
    "balance",
    "pending",
    "cost",
    "tax",
    "discount",
    "inventory",
)
_TIME_HINTS = ("date", "time", "created", "updated", "closed", "paid", "sold")
_STATUS_HINTS = ("status", "state", "stage")


def is_empty(value: Any) -> bool:
    return value is None or (isinstance(value, str) and value.strip() == "")


def normalize_value(value: Any) -> str | None:
    if is_empty(value):
        return None
    text = str(value).strip().lower()
    return text or None


def profile_values(
    *,
    field_id: str,
    asset_id: str,
    name: str,
    values: list[Any],
    row_count: int | None = None,
) -> FieldProfile:
    total_rows = row_count if row_count is not None else len(values)
    non_empty_values = [value for value in values if not is_empty(value)]
    blank_count = sum(1 for value in values if isinstance(value, str) and value.strip() == "")
    normalized = [normalize_value(value) for value in non_empty_values]
    normalized_values = [value for value in normalized if value is not None]
    distinct_values = sorted(set(normalized_values))
    parse_profile = parse_profile_for(non_empty_values)
    observed_type = infer_observed_type(parse_profile, non_empty_count=len(non_empty_values))
    top_values = _top_values(normalized_values)
    sample_values = _sample_values(non_empty_values)
    min_value, max_value = _min_max(non_empty_values, observed_type)
    null_rate = _ratio(max(total_rows - len(non_empty_values), 0), total_rows)
    blank_rate = _ratio(blank_count, total_rows)
    non_null_rate = _ratio(len(non_empty_values), total_rows)
    uniqueness_rate = _ratio(len(distinct_values), len(non_empty_values))
    quality_flags = _quality_flags(
        total_rows=total_rows,
        non_null_count=len(non_empty_values),
        distinct_count=len(distinct_values),
        blank_rate=blank_rate,
        observed_type=observed_type,
        parse=parse_profile,
    )
    candidates = field_candidates(
        name=name,
        observed_type=observed_type,
        non_null_count=len(non_empty_values),
        row_count=total_rows,
        distinct_count=len(distinct_values),
        uniqueness_rate=uniqueness_rate,
    )
    return FieldProfile(
        field_id=field_id,
        asset_id=asset_id,
        name=name,
        row_count=total_rows,
        non_null_count=len(non_empty_values),
        blank_count=blank_count,
        distinct_count=len(distinct_values),
        null_rate=round(null_rate, 4),
        blank_rate=round(blank_rate, 4),
        non_null_rate=round(non_null_rate, 4),
        uniqueness_rate=round(uniqueness_rate, 4),
        observed_type=observed_type,
        parse=parse_profile,
        sample_values=sample_values,
        top_values=top_values,
        min_value=min_value,
        max_value=max_value,
        candidates=candidates,
        quality_flags=quality_flags,
    )


def parse_profile_for(values: list[Any]) -> ParseProfile:
    texts = [str(value).strip() for value in values if not is_empty(value)]
    denominator = len(texts)
    return ParseProfile(
        integer_rate=_rate(texts, _is_integer, denominator),
        number_rate=_rate(texts, _is_number, denominator),
        money_rate=_rate(texts, _is_money, denominator),
        boolean_rate=_rate(texts, _is_boolean, denominator),
        date_rate=_rate(texts, _is_date, denominator),
        datetime_rate=_rate(texts, _is_datetime, denominator),
        email_rate=_rate(texts, _is_email, denominator),
        url_rate=_rate(texts, _is_url, denominator),
        json_rate=_rate(texts, _is_json, denominator),
    )


def infer_observed_type(parse: ParseProfile, *, non_empty_count: int) -> ObservedType:
    if non_empty_count == 0:
        return "unknown"
    if parse.boolean_rate >= 0.98:
        return "boolean"
    if parse.integer_rate >= 0.98:
        return "integer"
    if parse.number_rate >= 0.98:
        return "number"
    if parse.money_rate >= 0.98:
        return "money"
    if parse.date_rate >= 0.98:
        return "date"
    if parse.datetime_rate >= 0.98:
        return "datetime"
    if parse.email_rate >= 0.98:
        return "email"
    if parse.url_rate >= 0.98:
        return "url"
    if parse.json_rate >= 0.98:
        return "json"
    return "text"


def field_candidates(
    *,
    name: str,
    observed_type: ObservedType,
    non_null_count: int,
    row_count: int,
    distinct_count: int,
    uniqueness_rate: float,
) -> list[FieldCandidate]:
    if row_count <= 0 or non_null_count <= 0:
        return []
    lowered = name.lower()
    candidates: list[FieldCandidate] = []
    non_null_rate = _ratio(non_null_count, row_count)
    id_like = _has_hint(lowered, _ID_HINTS)
    measure_like = _has_hint(lowered, _MEASURE_HINTS)

    if uniqueness_rate >= 0.98 and non_null_rate >= 0.95 and non_null_count >= 3 and (id_like or not measure_like):
        confidence = 0.78 + (0.12 if id_like else 0.0)
        candidates.append(FieldCandidate(
            kind="primary_key",
            confidence=round(min(confidence, 0.95), 4),
            reasons=["high uniqueness", "mostly non-empty"] + (["identifier-like name"] if id_like else []),
        ))

    if id_like and uniqueness_rate < 0.98:
        candidates.append(FieldCandidate(
            kind="foreign_key",
            confidence=round(0.58 + (0.2 * non_null_rate), 4),
            reasons=["identifier-like name", "repeated values"],
        ))

    if observed_type in {"integer", "number", "money"} and measure_like:
        candidates.append(FieldCandidate(
            kind="measure",
            confidence=0.82,
            reasons=["numeric values", "measure-like name"],
        ))
    elif observed_type in {"integer", "number", "money"} and uniqueness_rate < 0.9:
        candidates.append(FieldCandidate(
            kind="measure",
            confidence=0.62,
            reasons=["numeric values"],
        ))

    if observed_type in {"date", "datetime"} or _has_hint(lowered, _TIME_HINTS):
        candidates.append(FieldCandidate(
            kind="timestamp",
            confidence=0.82 if observed_type in {"date", "datetime"} else 0.55,
            reasons=["time-like values" if observed_type in {"date", "datetime"} else "time-like name"],
        ))

    if observed_type in {"text", "email", "url"} and _has_hint(lowered, _LABEL_HINTS):
        candidates.append(FieldCandidate(
            kind="label",
            confidence=0.76,
            reasons=["label-like name", f"{observed_type} values"],
        ))

    if _has_hint(lowered, _STATUS_HINTS):
        candidates.append(FieldCandidate(
            kind="status",
            confidence=0.8,
            reasons=["status-like name"],
        ))

    if distinct_count <= max(3, min(50, int(row_count * 0.2))) and uniqueness_rate < 0.5:
        candidates.append(FieldCandidate(
            kind="category",
            confidence=0.66,
            reasons=["low cardinality"],
        ))

    if id_like:
        candidates.append(FieldCandidate(
            kind="identifier",
            confidence=0.7,
            reasons=["identifier-like name"],
        ))

    deduped: dict[str, FieldCandidate] = {}
    for candidate in candidates:
        current = deduped.get(candidate.kind)
        if current is None or candidate.confidence > current.confidence:
            deduped[candidate.kind] = candidate
    return sorted(deduped.values(), key=lambda item: item.confidence, reverse=True)


def candidate_confidence(profile: FieldProfile, kind: str) -> float:
    for candidate in profile.candidates:
        if candidate.kind == kind:
            return candidate.confidence
    return 0.0


def has_candidate(profile: FieldProfile, *kinds: str) -> bool:
    kinds_set = set(kinds)
    return any(candidate.kind in kinds_set for candidate in profile.candidates)


def _quality_flags(
    *,
    total_rows: int,
    non_null_count: int,
    distinct_count: int,
    blank_rate: float,
    observed_type: ObservedType,
    parse: ParseProfile,
) -> list[str]:
    flags: list[str] = []
    if total_rows == 0:
        return ["empty_asset"]
    if non_null_count == 0:
        flags.append("all_null")
    elif _ratio(non_null_count, total_rows) < 0.2:
        flags.append("mostly_null")
    if blank_rate > 0.2:
        flags.append("blank_heavy")
    if non_null_count > 0 and distinct_count == 1:
        flags.append("constant")
    if observed_type == "text":
        strongest_parse = max(
            parse.integer_rate,
            parse.number_rate,
            parse.money_rate,
            parse.boolean_rate,
            parse.date_rate,
            parse.datetime_rate,
            parse.email_rate,
            parse.url_rate,
            parse.json_rate,
        )
        if 0.2 <= strongest_parse < 0.98:
            flags.append("mixed_type")
    return flags


def _rate(texts: list[str], fn: Any, denominator: int) -> float:
    if denominator == 0:
        return 0.0
    return round(sum(1 for text in texts if fn(text)) / denominator, 4)


def _ratio(numerator: int | float, denominator: int | float) -> float:
    if denominator == 0:
        return 0.0
    return float(numerator) / float(denominator)


def _has_hint(name: str, hints: tuple[str, ...]) -> bool:
    parts = [part for part in re.split(r"[^a-z0-9]+", name.lower()) if part]
    return any(hint in parts or hint in name for hint in hints)


def _is_integer(text: str) -> bool:
    try:
        int(text.replace(",", ""))
        return True
    except ValueError:
        return False


def _is_number(text: str) -> bool:
    try:
        value = float(text.replace(",", ""))
        return math.isfinite(value)
    except ValueError:
        return False


def _is_money(text: str) -> bool:
    return bool(_MONEY_RE.match(text))


def _is_boolean(text: str) -> bool:
    return text.lower() in {"true", "false", "yes", "no", "0", "1"}


def _is_date(text: str) -> bool:
    normalized = _normalize_date_text(text)
    try:
        datetime.fromisoformat(normalized)
    except ValueError:
        return False
    return "t" not in normalized.lower() and len(normalized[:10]) == 10


def _is_datetime(text: str) -> bool:
    normalized = _normalize_date_text(text)
    try:
        datetime.fromisoformat(normalized)
        return True
    except ValueError:
        return False


def _normalize_date_text(text: str) -> str:
    candidate = text.strip().replace("Z", "+00:00")
    for sep in ("/", "."):
        candidate = candidate.replace(sep, "-")
    return candidate


def _is_email(text: str) -> bool:
    return bool(_EMAIL_RE.match(text))


def _is_url(text: str) -> bool:
    return bool(_URL_RE.match(text))


def _is_json(text: str) -> bool:
    if not text or text[0] not in "[{":
        return False
    try:
        json.loads(text)
        return True
    except ValueError:
        return False


def _top_values(values: list[str], limit: int = 10) -> list[dict[str, Any]]:
    return [
        {"value": value, "count": count}
        for value, count in Counter(values).most_common(limit)
    ]


def _sample_values(values: list[Any], limit: int = 10) -> list[Any]:
    samples: list[Any] = []
    seen: set[str] = set()
    for value in values:
        key = str(value)
        if key in seen:
            continue
        seen.add(key)
        samples.append(value)
        if len(samples) >= limit:
            break
    return samples


def _min_max(values: list[Any], observed_type: ObservedType) -> tuple[Any, Any]:
    if not values:
        return None, None
    if observed_type in {"integer", "number", "money"}:
        parsed: list[float] = []
        for value in values:
            number = _parse_number(value)
            if number is not None:
                parsed.append(number)
        return (min(parsed), max(parsed)) if parsed else (None, None)
    texts = [str(value).strip() for value in values if not is_empty(value)]
    return (min(texts), max(texts)) if texts else (None, None)


def _parse_number(value: Any) -> float | None:
    text = str(value).strip()
    text = re.sub(r"^[₹$€£]\s*", "", text).replace(",", "")
    try:
        number = float(text)
    except ValueError:
        return None
    return number if math.isfinite(number) else None
