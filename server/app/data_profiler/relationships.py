"""Deterministic relationship evidence helpers."""

from __future__ import annotations

from app.data_profiler.contracts import FieldProfile, RelationshipCardinality, RelationshipProfile
from app.data_profiler.inference import has_candidate

_JOINABLE_TYPES = {"text", "integer", "email", "url"}


def is_join_candidate(profile: FieldProfile) -> bool:
    if profile.non_null_count < 2:
        return False
    if profile.observed_type not in _JOINABLE_TYPES:
        return False
    if has_candidate(profile, "primary_key", "foreign_key", "identifier", "label"):
        return True
    lowered = profile.name.lower()
    return any(token in lowered for token in ("id", "key", "code", "email", "sku", "name"))


def relationship_profile(
    *,
    left: FieldProfile,
    right: FieldProfile,
    shared_values: list[str],
) -> RelationshipProfile | None:
    if left.asset_id == right.asset_id:
        return None
    if not is_join_candidate(left) or not is_join_candidate(right):
        return None
    denominator = min(left.distinct_count, right.distinct_count)
    if denominator <= 0:
        return None
    shared_count = len(shared_values)
    overlap = shared_count / denominator
    min_shared = 1 if denominator <= 5 else 3
    if shared_count < min_shared:
        return None
    if overlap < (0.8 if denominator <= 5 else 0.45):
        return None

    type_weight = 1.0 if left.observed_type == right.observed_type else 0.78
    name_weight = _name_weight(left.name, right.name)
    key_weight = _key_weight(left, right)
    confidence = min(0.98, overlap * type_weight * name_weight * key_weight)
    if confidence < 0.4:
        return None

    return RelationshipProfile(
        left_asset_id=left.asset_id,
        left_field_id=left.field_id,
        right_asset_id=right.asset_id,
        right_field_id=right.field_id,
        cardinality=_cardinality(left, right),
        overlap_ratio=round(overlap, 4),
        shared_value_count=shared_count,
        confidence=round(confidence, 4),
        sample_shared_values=shared_values[:10],
        reasons=_reasons(left, right, overlap=overlap, type_weight=type_weight),
    )


def _cardinality(left: FieldProfile, right: FieldProfile) -> RelationshipCardinality:
    left_unique = left.uniqueness_rate >= 0.98 and left.non_null_rate >= 0.9
    right_unique = right.uniqueness_rate >= 0.98 and right.non_null_rate >= 0.9
    if left_unique and right_unique:
        return "one_to_one"
    if left_unique:
        return "one_to_many"
    if right_unique:
        return "many_to_one"
    return "many_to_many"


def _name_weight(left_name: str, right_name: str) -> float:
    left = left_name.lower()
    right = right_name.lower()
    if left == right:
        return 1.12
    if left.endswith("_id") and right == "id":
        return 1.08
    if right.endswith("_id") and left == "id":
        return 1.08
    shared_tokens = set(left.replace("-", "_").split("_")) & set(right.replace("-", "_").split("_"))
    return 1.04 if shared_tokens else 0.95


def _key_weight(left: FieldProfile, right: FieldProfile) -> float:
    if has_candidate(left, "primary_key", "foreign_key") or has_candidate(right, "primary_key", "foreign_key"):
        return 1.08
    if has_candidate(left, "label") and has_candidate(right, "label"):
        return 0.88
    return 1.0


def _reasons(left: FieldProfile, right: FieldProfile, *, overlap: float, type_weight: float) -> list[str]:
    reasons = [f"{round(overlap * 100)}% distinct-value overlap"]
    if left.observed_type == right.observed_type:
        reasons.append(f"matching observed type: {left.observed_type}")
    elif type_weight < 1.0:
        reasons.append(f"compatible but different observed types: {left.observed_type}/{right.observed_type}")
    if has_candidate(left, "primary_key", "foreign_key", "identifier"):
        reasons.append(f"left {left.name} is key-like")
    if has_candidate(right, "primary_key", "foreign_key", "identifier"):
        reasons.append(f"right {right.name} is key-like")
    return reasons
