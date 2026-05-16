"""Autonomous business-memory candidate extraction."""

from __future__ import annotations

import hashlib

from app.agent_plane.contracts import (
    AssetRole,
    BusinessGraph,
    BusinessModel,
    FieldRole,
    PatternBatch,
)
from app.memory_plane.contracts import MemoryCandidate

_MIN_AUTO_CONFIDENCE = 0.7


def candidates_from_agent_artifacts(
    *,
    business_model: BusinessModel,
    asset_roles: list[AssetRole],
    field_roles: list[FieldRole],
    business_graph: BusinessGraph,
    patterns: PatternBatch | None = None,
) -> list[MemoryCandidate]:
    """Create stable business-memory candidates from structured agent outputs.

    This intentionally avoids result rows, metric values, and narrative prose.
    Only reusable business semantics become memory.
    """
    candidates: list[MemoryCandidate] = []
    if business_model.confidence >= _MIN_AUTO_CONFIDENCE:
        candidates.append(
            MemoryCandidate(
                key="business_summary",
                kind="business_summary",
                scope="org",
                statement=business_model.paragraph,
                confidence=business_model.confidence,
                metadata={
                    "business_kind": business_model.business_kind,
                    "primary_currency": business_model.primary_currency,
                    "useful_lenses": business_model.useful_lenses,
                },
            )
        )

    for entity in business_model.entities:
        candidates.append(
            MemoryCandidate(
                key=f"business_entity:{_slug(entity.name)}",
                kind="business_entity",
                scope="asset",
                subject_ref={
                    "entity": entity.name,
                    "primary_asset_id": entity.primary_asset_id,
                    "related_asset_ids": entity.related_asset_ids,
                },
                statement=entity.description,
                evidence_refs=[{"asset_id": entity.primary_asset_id}],
                confidence=business_model.confidence,
                metadata={"plural": entity.plural},
            )
        )

    for kpi in business_model.primary_kpis:
        key = f"business_kpi:{_slug(kpi.name)}:{_short_hash(':'.join(kpi.field_refs + kpi.source_asset_ids))}"
        candidates.append(
            MemoryCandidate(
                key=key,
                kind="business_kpi",
                scope="org",
                subject_ref={
                    "field_refs": kpi.field_refs,
                    "source_asset_ids": kpi.source_asset_ids,
                },
                statement=kpi.description,
                evidence_refs=[
                    {"field_id": field_id} for field_id in kpi.field_refs
                ] + [
                    {"asset_id": asset_id} for asset_id in kpi.source_asset_ids
                ],
                confidence=business_model.confidence,
                metadata={"name": kpi.name},
            )
        )

    for role in asset_roles:
        if role.confidence < _MIN_AUTO_CONFIDENCE:
            continue
        candidates.append(
            MemoryCandidate(
                key=f"asset_role:{role.asset_id}",
                kind="asset_role",
                scope="asset",
                subject_ref={
                    "asset_id": role.asset_id,
                    "role": role.role,
                    "entity_type": role.entity_type,
                },
                statement=role.why,
                evidence_refs=[{"asset_id": role.asset_id}],
                confidence=role.confidence,
                metadata={"label": role.label, "tags": role.tags},
            )
        )

    for field_role in field_roles:
        if field_role.confidence < _MIN_AUTO_CONFIDENCE or field_role.role == "unknown":
            continue
        candidates.append(
            MemoryCandidate(
                key=f"field_role:{field_role.field_id}",
                kind="field_role",
                scope="field",
                subject_ref={
                    "field_id": field_role.field_id,
                    "asset_id": field_role.asset_id,
                    "field_name": field_role.field_name,
                    "role": field_role.role,
                    "semantic_type": field_role.semantic_type,
                    "entity_hint": field_role.entity_hint,
                    "measure_kind": field_role.measure_kind,
                },
                statement=field_role.why,
                evidence_refs=[{"field_id": field_role.field_id, "asset_id": field_role.asset_id}],
                confidence=field_role.confidence,
            )
        )

    for edge in business_graph.edges:
        if edge.confidence < _MIN_AUTO_CONFIDENCE:
            continue
        left, right = sorted([edge.left_field_id, edge.right_field_id])
        candidates.append(
            MemoryCandidate(
                key=f"relationship:{left}:{right}",
                kind="relationship",
                scope="relationship",
                subject_ref={
                    "left_entity": edge.left_entity,
                    "left_asset_id": edge.left_asset_id,
                    "left_field_id": edge.left_field_id,
                    "right_entity": edge.right_entity,
                    "right_asset_id": edge.right_asset_id,
                    "right_field_id": edge.right_field_id,
                    "cardinality": edge.cardinality,
                },
                statement=edge.meaning,
                evidence_refs=[
                    {"data_graph_edge_id": edge_id}
                    for edge_id in edge.evidence_edge_ids
                ],
                confidence=edge.confidence,
            )
        )

    if patterns is not None:
        for hypothesis in patterns.hypotheses:
            if hypothesis.priority < _MIN_AUTO_CONFIDENCE:
                continue
            candidates.append(
                MemoryCandidate(
                    key=f"validated_pattern:{_slug(hypothesis.pattern_type)}:{hypothesis.target_asset_id}",
                    kind="validated_pattern",
                    scope="pattern",
                    subject_ref={
                        "hypothesis_id": hypothesis.hypothesis_id,
                        "pattern_type": hypothesis.pattern_type,
                        "target_entity": hypothesis.target_entity,
                        "target_asset_id": hypothesis.target_asset_id,
                    },
                    statement=hypothesis.why_this_matters,
                    evidence_refs=[{"asset_id": hypothesis.target_asset_id}],
                    confidence=hypothesis.priority,
                    metadata={"question": hypothesis.question},
                )
            )

    return _dedupe(candidates)


def _dedupe(candidates: list[MemoryCandidate]) -> list[MemoryCandidate]:
    by_key: dict[str, MemoryCandidate] = {}
    for candidate in candidates:
        existing = by_key.get(candidate.key)
        if existing is None or candidate.confidence > existing.confidence:
            by_key[candidate.key] = candidate
    return list(by_key.values())


def _slug(value: str) -> str:
    cleaned = "".join(char.lower() if char.isalnum() else "_" for char in value).strip("_")
    return "_".join(part for part in cleaned.split("_") if part) or "memory"


def _short_hash(value: str) -> str:
    return hashlib.sha1(value.encode("utf-8")).hexdigest()[:8]
