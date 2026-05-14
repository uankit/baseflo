"""Adaptive operating intelligence read model.

This module builds the first durable Business OS layer from connected data:
assets, columns, relationships, metrics, insights, memories, actions, and
audit events. It intentionally avoids vertical templates. The deterministic
logic here profiles structure and computes evidence; LLM agents can later use
this read model to make richer semantic decisions.
"""

from __future__ import annotations

import asyncio
import math
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field
from sqlalchemy import delete, select

from app.core.context import TenantCtx
from app.db.models import (
    ActionProposal,
    AuditEvent,
    BusinessMemory,
    DataSource,
    Insight,
    MetricDefinition,
    MetricValue,
    OperatingAsset,
    OperatingColumn,
    OperatingRelationship,
)
from app.db.session import open_session
from app.substrate import qualified_name, safe_query

_GENERATOR = "operating_intelligence_v1"
_SAMPLE_LIMIT = 200
_MAX_SAMPLE_VALUES = 8


class OperatingSummary(BaseModel):
    assets: int = 0
    columns: int = 0
    relationships: int = 0
    metrics: int = 0
    open_insights: int = 0
    proposed_actions: int = 0
    memories: int = 0
    last_built_at: str | None = None


class OperatingBrief(BaseModel):
    summary: OperatingSummary
    business: dict[str, Any] = Field(default_factory=dict)
    assets: list[dict[str, Any]]
    relationships: list[dict[str, Any]]
    metrics: list[dict[str, Any]]
    insights: list[dict[str, Any]]
    memories: list[dict[str, Any]]
    actions: list[dict[str, Any]]


class RememberInput(BaseModel):
    key: str = Field(min_length=1, max_length=255)
    value: str = Field(min_length=1)


@dataclass(frozen=True)
class _ColumnProfile:
    name: str
    observed_type: str
    semantic_type: str
    null_rate: float
    unique_count: int
    confidence: float
    sample_values: list[Any]
    normalized_values: frozenset[str]
    non_null_count: int
    profile: dict[str, Any]


@dataclass(frozen=True)
class _AssetProfile:
    asset: OperatingAsset
    qualified_name: str
    table_label: str
    row_count: int
    columns: list[_ColumnProfile]


def _quote_ident(value: str) -> str:
    return '"' + value.replace('"', '""') + '"'


def _currency(value: float | None, currency: str | None = None) -> str:
    if value is None:
        return "Unknown"
    suffix = f" {currency}" if currency else ""
    if abs(value) >= 1_000_000:
        return f"{value / 1_000_000:.1f}M{suffix}"
    if abs(value) >= 1_000:
        return f"{value / 1_000:.1f}K{suffix}"
    return f"{value:,.0f}{suffix}"


def _short_number(value: float | int | None) -> str:
    if value is None:
        return "Unknown"
    if abs(value) >= 1_000_000:
        return f"{value / 1_000_000:.1f}M"
    if abs(value) >= 1_000:
        return f"{value / 1_000:.1f}K"
    return f"{value:,.0f}"


def _asset_domain(asset: OperatingAsset) -> tuple[str, str, str]:
    role = asset.profile.get("agentic_role") or {}
    domain = str(role.get("role") or "unclassified")
    entity_type = str(role.get("entity_type") or asset.table_label or asset.qualified_name)
    label = entity_type.replace("_", " ").title()
    why = str(role.get("why") or "Connected source profiled by the operating runtime.")
    return (domain, label, why)


def _business_edge_label(left_domain: str, right_domain: str, column_hint: str) -> str:
    return f"{left_domain} connects to {right_domain} through {column_hint}"


async def _business_query(
    org_id: UUID, sql: str, *, max_rows: int = 20,
) -> list[dict[str, Any]]:
    try:
        return await asyncio.to_thread(safe_query, org_id, sql, max_rows=max_rows)
    except Exception:
        return []


def _find_asset(assets: list[OperatingAsset], *needles: str) -> OperatingAsset | None:
    for asset in assets:
        haystack = f"{asset.table_label} {asset.qualified_name}".lower()
        if all(needle.lower() in haystack for needle in needles):
            return asset
    return None


def _humanize(text: str | None, fallback: str = "") -> str:
    if not text:
        return fallback
    return text.replace("_", " ").strip().title()


def _format_value(value: float | None) -> str:
    if value is None:
        return "—"
    if abs(value) >= 1_000_000:
        return f"{value / 1_000_000:.1f}M"
    if abs(value) >= 1_000:
        return f"{value / 1_000:.1f}K"
    if abs(value) >= 10:
        return f"{value:,.0f}"
    return f"{value:,.2f}"


def _load_json_memory(memories: list[BusinessMemory], key: str) -> dict[str, Any]:
    import json
    memory = next((m for m in memories if m.key == key and isinstance(m.value, str)), None)
    if memory is None or not memory.value:
        return {}
    try:
        return json.loads(memory.value)
    except Exception:
        return {}


async def _build_business_view(
    ctx: TenantCtx,
    *,
    assets: list[OperatingAsset],
    relationships: list[OperatingRelationship],
    asset_label_by_id: dict[UUID, str],
    asset_qname_by_id: dict[UUID, str],
    insights: list[Insight] | None = None,
    actions: list[ActionProposal] | None = None,
    metrics: list[MetricDefinition] | None = None,
    columns_by_asset: dict[UUID, list[OperatingColumn]] | None = None,
    memories: list[BusinessMemory] | None = None,
) -> dict[str, Any]:
    """Operator-facing read model.

    Every business sentence on this surface comes from an agent. The runtime
    only profiles columns and runs SQL. The brief reads three agent-produced
    BusinessMemory rows:
      - "business_model"     — Phase 1 paragraph + structured model
      - "cross_team_report"  — alignment/conflict/gap/handoffs
      - "founder_brief"      — headline/dek/signals/team_bylines/questions

    Plus the per-team insights persisted as Insight rows and the actions
    persisted as ActionProposal rows.
    """
    insights = insights or []
    actions = actions or []
    memories = memories or []

    if not assets:
        return {
            "brief": {
                "title": "Connect a source to see your business",
                "summary": (
                    "Baseflo reads your data and tells you what every team would say at the morning standup."
                ),
                "signals": [],
                "top_insights": [],
                "action_backlog": [],
                "source_health": [],
                "business_model": {},
                "cross_team": {},
            },
            "lenses": [],
            "graph": {"nodes": [], "edges": []},
            "recommended_questions": [],
        }

    open_insights = [insight for insight in insights if insight.status == "open"]
    proposed_actions = [action for action in actions if action.status == "proposed"]
    business_insights = [
        insight
        for insight in open_insights
        if insight.kind not in {"business_map", "data_quality", "starter"}
    ]

    business_model = _load_json_memory(memories, "business_model")
    cross_team = _load_json_memory(memories, "cross_team_report")
    founder_brief = _load_json_memory(memories, "founder_brief")

    title = (
        founder_brief.get("headline")
        or business_model.get("paragraph", "").split(".")[0]
        or (business_insights[0].title if business_insights else "Reading your business")
    )
    summary = (
        founder_brief.get("dek")
        or business_model.get("paragraph")
        or (business_insights[0].summary if business_insights else "Baseflo is reading the data.")
    )

    signals: list[dict[str, Any]] = list(founder_brief.get("signals") or [])
    if not signals:
        signals = [
            {
                "label": "Connected sources",
                "value": _format_value(float(len({a.source_name for a in assets}))),
                "detail": f"{_format_value(float(sum(a.row_count for a in assets)))} records mirrored",
                "tone": "neutral",
            },
            {
                "label": "Inferences",
                "value": _format_value(float(len(business_insights))),
                "detail": "Across all teams",
                "tone": "neutral",
            },
            {
                "label": "Actions waiting",
                "value": _format_value(float(len(proposed_actions))),
                "detail": "Drafted by team agents",
                "tone": "neutral",
            },
        ]

    # Group insights by team_id so the frontend can render team bylines.
    insights_by_team: dict[str, list[dict[str, Any]]] = {}
    top_insights: list[dict[str, Any]] = []
    for insight in business_insights:
        ev = insight.evidence if isinstance(insight.evidence, dict) else {}
        team_id = (
            (insight.source or {}).get("team_id")
            if isinstance(insight.source, dict)
            else None
        ) or ev.get("team_id")
        record = {
            "id": str(insight.id),
            "title": insight.title,
            "summary": insight.summary,
            "why": ev.get("why"),
            "tags": ev.get("tags") or [],
            "result_preview": ev.get("result_preview") or [],
            "interpretation": ev.get("interpretation") or {},
            "lineage": ev.get("lineage") or [],
            "team_id": team_id,
            "confidence": insight.confidence,
            "impact_score": insight.impact_score,
        }
        top_insights.append(record)
        if team_id:
            insights_by_team.setdefault(team_id, []).append(record)

    # Team bylines from the founder brief (preferred) or auto from insights.
    team_bylines: list[dict[str, Any]] = list(founder_brief.get("team_bylines") or [])
    if not team_bylines:
        for team_id, team_records in insights_by_team.items():
            team_bylines.append({
                "team_id": team_id,
                "standup_summary": team_records[0]["summary"] if team_records else "",
                "insight_ids": [r["id"] for r in team_records[:3]],
            })

    action_backlog: list[dict[str, Any]] = []
    for action in proposed_actions[:12]:
        payload = action.proposed_payload if isinstance(action.proposed_payload, dict) else {}
        action_backlog.append({
            "id": str(action.id),
            "title": action.title,
            "summary": action.summary,
            "why": payload.get("why") or action.summary,
            "kind": action.kind,
            "team_id": payload.get("team_id"),
            "execution_mode": payload.get("execution_mode"),
            "risk": payload.get("risk"),
        })

    source_health: list[dict[str, Any]] = []
    for asset in assets:
        role_dump = (asset.profile or {}).get("agentic_role") if isinstance(asset.profile, dict) else None
        role = role_dump if isinstance(role_dump, dict) else {}
        source_health.append({
            "label": asset.table_label,
            "source": asset.source_name.replace("_", " ").title() if asset.source_name else None,
            "rows": asset.row_count,
            "status": asset.status,
            "role": role.get("role"),
            "entity_type": role.get("entity_type"),
            "tags": role.get("tags") or [],
            "why": role.get("why"),
        })

    # Tag lenses — derived from agent-emitted tags only.
    tag_counts: dict[str, int] = {}
    for insight in business_insights:
        ev = insight.evidence if isinstance(insight.evidence, dict) else {}
        for tag in ev.get("tags") or []:
            tag_counts[str(tag)] = tag_counts.get(str(tag), 0) + 1
    lenses = [
        {"id": tag, "title": _humanize(tag, tag), "count": count}
        for tag, count in sorted(tag_counts.items(), key=lambda item: item[1], reverse=True)[:6]
    ]

    return {
        "brief": {
            "title": title,
            "summary": summary,
            "signals": signals[:4],
            "top_insights": top_insights,
            "action_backlog": action_backlog,
            "source_health": source_health,
            "business_model": {
                "paragraph": business_model.get("paragraph"),
                "business_kind": business_model.get("business_kind"),
                "primary_currency": business_model.get("primary_currency"),
                "entities": business_model.get("entities", []),
                "assumptions": business_model.get("assumptions", []),
                "missing_or_failed_sources": business_model.get("missing_or_failed_sources", []),
                "primary_kpis": business_model.get("primary_kpis", []),
            },
            "cross_team": {
                "standup_summary": cross_team.get("standup_summary"),
                "alignments": cross_team.get("alignments", []),
                "conflicts": cross_team.get("conflicts", []),
                "gaps": cross_team.get("gaps", []),
                "handoffs": cross_team.get("handoffs", []),
            },
            "team_bylines": team_bylines,
        },
        "lenses": lenses,
        "graph": {"nodes": [], "edges": []},
        "recommended_questions": list(founder_brief.get("questions") or []),
    }


def _metric_key(*parts: str) -> str:
    raw = "__".join(parts).lower()
    safe = "".join(ch if ch.isalnum() else "_" for ch in raw)
    return "_".join(part for part in safe.split("_") if part)[:220]


def _is_empty(value: Any) -> bool:
    return value is None or (isinstance(value, str) and value.strip() == "")


def _normalize(value: Any) -> str | None:
    if _is_empty(value):
        return None
    text = str(value).strip().lower()
    return text if text else None


def _is_int(text: str) -> bool:
    try:
        int(text.replace(",", ""))
        return True
    except ValueError:
        return False


def _is_float(text: str) -> bool:
    try:
        value = float(text.replace(",", ""))
        return math.isfinite(value)
    except ValueError:
        return False


def _is_datetime_like(text: str) -> bool:
    candidate = text.strip().replace("Z", "+00:00")
    for sep in ("/", "."):
        candidate = candidate.replace(sep, "-")
    try:
        datetime.fromisoformat(candidate)
        return True
    except ValueError:
        return False


def _infer_observed_type(non_empty_values: list[Any]) -> str:
    if not non_empty_values:
        return "unknown"
    texts = [str(v).strip() for v in non_empty_values if not _is_empty(v)]
    if not texts:
        return "unknown"

    sample = texts[:50]
    if all(t.lower() in {"true", "false", "yes", "no", "0", "1"} for t in sample):
        return "boolean"
    if all(_is_int(t) for t in sample):
        return "integer"
    if all(_is_float(t) for t in sample):
        return "number"
    if all(_is_datetime_like(t) for t in sample):
        return "datetime"
    if all("@" in t and "." in t.rsplit("@", 1)[-1] for t in sample):
        return "email"
    if all(t.startswith(("http://", "https://")) for t in sample):
        return "url"
    return "text"


def _semantic_type(
    observed_type: str, *, non_null_count: int, unique_count: int, sample_size: int
) -> tuple[str, float]:
    if non_null_count == 0:
        return "unknown", 0.0

    unique_ratio = unique_count / max(non_null_count, 1)
    if unique_ratio >= 0.98 and non_null_count >= 3:
        return "identity_candidate", 0.72
    if observed_type in {"datetime", "date"}:
        return "temporal_candidate", 0.74
    if observed_type in {"integer", "number"}:
        return "measure_candidate", 0.62
    if observed_type in {"email", "url"}:
        return observed_type, 0.8
    if unique_count <= max(3, min(20, int(sample_size * 0.35))):
        return "category_candidate", 0.58
    return "descriptor_candidate", 0.46


def _profile_column(name: str, rows: list[dict[str, Any]]) -> _ColumnProfile:
    values = [row.get(name) for row in rows]
    non_empty_values = [v for v in values if not _is_empty(v)]
    normalized = [_normalize(v) for v in non_empty_values]
    normalized_set = frozenset(v for v in normalized if v is not None)
    observed_type = _infer_observed_type(non_empty_values)
    semantic_type, confidence = _semantic_type(
        observed_type,
        non_null_count=len(non_empty_values),
        unique_count=len(normalized_set),
        sample_size=max(len(rows), 1),
    )
    null_rate = 1.0 - (len(non_empty_values) / max(len(rows), 1)) if rows else 0.0
    samples: list[Any] = []
    seen: set[str] = set()
    for value in non_empty_values:
        key = str(value)
        if key in seen:
            continue
        seen.add(key)
        samples.append(value)
        if len(samples) >= _MAX_SAMPLE_VALUES:
            break
    return _ColumnProfile(
        name=name,
        observed_type=observed_type,
        semantic_type=semantic_type,
        null_rate=round(null_rate, 4),
        unique_count=len(normalized_set),
        confidence=confidence,
        sample_values=samples,
        normalized_values=normalized_set,
        non_null_count=len(non_empty_values),
        profile={
            "sample_size": len(rows),
            "non_null_count": len(non_empty_values),
            "unique_ratio": (
                round(len(normalized_set) / len(non_empty_values), 4)
                if non_empty_values
                else 0.0
            ),
        },
    )


async def _sample_rows(org_id: UUID, qualified_table_name: str) -> tuple[int, list[dict[str, Any]]]:
    count_sql = f"SELECT count(*) AS value FROM {_quote_ident(qualified_table_name)}"
    sample_sql = f"SELECT * FROM {_quote_ident(qualified_table_name)} LIMIT {_SAMPLE_LIMIT}"

    try:
        count_rows = await asyncio.to_thread(safe_query, org_id, count_sql, max_rows=1)
        row_count = int(count_rows[0]["value"]) if count_rows else 0
        rows = await asyncio.to_thread(
            safe_query, org_id, sample_sql, max_rows=_SAMPLE_LIMIT
        )
        return row_count, rows
    except Exception:
        return 0, []


def _relationship_kind(left: _ColumnProfile, right: _ColumnProfile) -> str:
    left_unique = left.unique_count == left.non_null_count and left.non_null_count > 0
    right_unique = right.unique_count == right.non_null_count and right.non_null_count > 0
    if left_unique and right_unique:
        return "one_to_one_candidate"
    if left_unique:
        return "one_to_many_candidate"
    if right_unique:
        return "many_to_one_candidate"
    return "many_to_many_candidate"


def _relationship_candidates(
    profiles: list[_AssetProfile],
) -> list[tuple[_AssetProfile, _AssetProfile, _ColumnProfile, _ColumnProfile, float, dict[str, Any]]]:
    candidates: list[
        tuple[_AssetProfile, _AssetProfile, _ColumnProfile, _ColumnProfile, float, dict[str, Any]]
    ] = []
    for idx, left_asset in enumerate(profiles):
        for right_asset in profiles[idx + 1 :]:
            for left_col in left_asset.columns:
                if left_col.non_null_count < 3:
                    continue
                for right_col in right_asset.columns:
                    if right_col.non_null_count < 3:
                        continue
                    shared = left_col.normalized_values & right_col.normalized_values
                    denominator = min(
                        len(left_col.normalized_values),
                        len(right_col.normalized_values),
                    )
                    if denominator == 0:
                        continue
                    overlap = len(shared) / denominator
                    type_match = left_col.observed_type == right_col.observed_type
                    confidence = overlap * (1.0 if type_match else 0.75)
                    if len(shared) >= 3 and confidence >= 0.45:
                        candidates.append(
                            (
                                left_asset,
                                right_asset,
                                left_col,
                                right_col,
                                round(confidence, 4),
                                {
                                    "overlap_ratio": round(overlap, 4),
                                    "shared_value_count": len(shared),
                                    "type_match": type_match,
                                    "sample_shared_values": sorted(shared)[:5],
                                },
                            )
                        )
    candidates.sort(key=lambda c: c[4], reverse=True)
    return candidates[:30]


async def _compute_metric_value(
    org_id: UUID, metric: MetricDefinition,
) -> tuple[float | None, dict[str, Any]]:
    try:
        rows = await asyncio.to_thread(
            safe_query, org_id, metric.expression_sql, max_rows=1
        )
    except Exception as exc:
        return None, {"error": str(exc), "sql": metric.expression_sql}
    if not rows:
        return None, {"sql": metric.expression_sql}
    raw_value = rows[0].get("value")
    try:
        value = float(raw_value) if raw_value is not None else None
    except (TypeError, ValueError):
        value = None
    return value, {"sql": metric.expression_sql, "row": rows[0]}


def _audit(
    ctx: TenantCtx,
    *,
    action: str,
    target_type: str,
    target_id: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> AuditEvent:
    return AuditEvent(
        organization_id=ctx.organization_id,
        actor_user_id=ctx.user_id,
        actor_type="user",
        action=action,
        target_type=target_type,
        target_id=target_id,
        metadata_=metadata or {},
        occurred_at=datetime.now(UTC),
    )


async def rebuild_operating_intelligence(ctx: TenantCtx) -> OperatingBrief:
    """Rebuild the operating read model from the current connected sources."""
    now = datetime.now(UTC)

    async with open_session() as session:
        result = await session.execute(
            select(DataSource)
            .where(DataSource.organization_id == ctx.organization_id)
            .order_by(DataSource.created_at.asc())
        )
        sources = list(result.scalars().all())

        await session.execute(
            delete(ActionProposal).where(ActionProposal.organization_id == ctx.organization_id)
        )
        await session.execute(delete(Insight).where(Insight.organization_id == ctx.organization_id))
        await session.execute(
            delete(MetricValue).where(MetricValue.organization_id == ctx.organization_id)
        )
        await session.execute(
            delete(MetricDefinition).where(MetricDefinition.organization_id == ctx.organization_id)
        )
        await session.execute(
            delete(OperatingRelationship).where(
                OperatingRelationship.organization_id == ctx.organization_id
            )
        )
        await session.execute(
            delete(OperatingColumn).where(OperatingColumn.organization_id == ctx.organization_id)
        )
        await session.execute(
            delete(OperatingAsset).where(OperatingAsset.organization_id == ctx.organization_id)
        )

        asset_profiles: list[_AssetProfile] = []
        total_columns = 0

        for source in sources:
            schema = source.discovered_schema or {}
            for table_info in schema.get("tables", []):
                table_name = table_info["name"]
                table_label = table_info.get("label") or table_name
                table_metadata = (
                    table_info.get("metadata")
                    if isinstance(table_info.get("metadata"), dict)
                    else {}
                )
                qname = qualified_name(source.name, table_name)
                row_count, rows = await _sample_rows(ctx.organization_id, qname)
                declared_columns = [c["name"] for c in table_info.get("columns", [])]
                row_columns = list(rows[0].keys()) if rows else []
                column_names = list(dict.fromkeys([*declared_columns, *row_columns]))

                asset = OperatingAsset(
                    organization_id=ctx.organization_id,
                    data_source_id=source.id,
                    qualified_name=qname,
                    source_name=source.name,
                    table_label=table_label,
                    row_count=row_count,
                    column_count=len(column_names),
                    status="active" if source.last_error is None else "degraded",
                    profile={
                        "source_kind": source.kind,
                        "source_status": source.status.value,
                        "sample_size": len(rows),
                        "source_metadata": table_metadata,
                        "generator": _GENERATOR,
                    },
                    last_profiled_at=now,
                )
                session.add(asset)
                await session.flush()

                column_profiles = [_profile_column(name, rows) for name in column_names]
                total_columns += len(column_profiles)
                for col in column_profiles:
                    session.add(
                        OperatingColumn(
                            organization_id=ctx.organization_id,
                            asset_id=asset.id,
                            name=col.name,
                            observed_type=col.observed_type,
                            semantic_type=col.semantic_type,
                            null_rate=col.null_rate,
                            unique_count=col.unique_count,
                            confidence=col.confidence,
                            sample_values=col.sample_values,
                            profile=col.profile,
                        )
                    )

                asset_profiles.append(
                    _AssetProfile(
                        asset=asset,
                        qualified_name=qname,
                        table_label=table_label,
                        row_count=row_count,
                        columns=column_profiles,
                    )
                )

        relationships = _relationship_candidates(asset_profiles)
        for left_asset, right_asset, left_col, right_col, confidence, evidence in relationships:
            session.add(
                OperatingRelationship(
                    organization_id=ctx.organization_id,
                    left_asset_id=left_asset.asset.id,
                    right_asset_id=right_asset.asset.id,
                    left_column=left_col.name,
                    right_column=right_col.name,
                    relationship_kind=_relationship_kind(left_col, right_col),
                    status="candidate",
                    confidence=confidence,
                    evidence={**evidence, "generator": _GENERATOR},
                )
            )

        metrics: list[MetricDefinition] = []
        for profile in asset_profiles:
            qtable = _quote_ident(profile.qualified_name)
            row_metric = MetricDefinition(
                organization_id=ctx.organization_id,
                asset_id=profile.asset.id,
                key=_metric_key("row_count", profile.qualified_name),
                name=f"{profile.table_label} rows",
                description=(
                    "Tracks the number of rows currently mirrored for this asset. "
                    "This is structural, data-grounded, and does not assume a business template."
                ),
                metric_type="row_count",
                expression_sql=f"SELECT count(*) AS value FROM {qtable}",
                status="active",
                confidence=0.9,
                definition={
                    "asset": profile.qualified_name,
                    "generator": _GENERATOR,
                    "lineage": [{"table": profile.qualified_name}],
                },
                created_by="system",
            )
            session.add(row_metric)
            metrics.append(row_metric)

            for col in profile.columns:
                if col.semantic_type != "measure_candidate" or col.non_null_count < 3:
                    continue
                qcol = _quote_ident(col.name)
                for agg, label in (("sum", "Total"), ("avg", "Average")):
                    metric = MetricDefinition(
                        organization_id=ctx.organization_id,
                        asset_id=profile.asset.id,
                        key=_metric_key(agg, profile.qualified_name, col.name),
                        name=f"{label} {col.name} in {profile.table_label}",
                        description=(
                            "Candidate metric generated because the column profiles as numeric. "
                            "It should be confirmed or dismissed by the user before it drives actions."
                        ),
                        metric_type=f"numeric_{agg}",
                        expression_sql=(
                            f"SELECT {agg}(try_cast({qcol} AS DOUBLE)) AS value FROM {qtable}"
                        ),
                        status="candidate",
                        confidence=0.55,
                        definition={
                            "asset": profile.qualified_name,
                            "column": col.name,
                            "aggregation": agg,
                            "generator": _GENERATOR,
                            "lineage": [{"table": profile.qualified_name, "column": col.name}],
                        },
                        created_by="system",
                    )
                    session.add(metric)
                    metrics.append(metric)

        await session.flush()

        for metric in metrics:
            value, evidence = await _compute_metric_value(ctx.organization_id, metric)
            session.add(
                MetricValue(
                    organization_id=ctx.organization_id,
                    metric_id=metric.id,
                    value=value,
                    computed_at=now,
                    evidence={**evidence, "generator": _GENERATOR},
                )
            )

        # Note: structural insights (business_map, data_quality) used to be created here.
        # They told the user about the engine, not about their business, so they are gone.
        # The agentic scan creates business-meaningful insights below; sparse-column
        # diagnostics live behind a future Sources health drawer if we need them.

        session.add(
            _audit(
                ctx,
                action="operating_intelligence.rebuild",
                target_type="organization",
                target_id=str(ctx.organization_id),
                metadata={
                    "assets": len(asset_profiles),
                    "relationships": len(relationships),
                    "metrics": len(metrics),
                },
            )
        )

    from app.agentic import run_operating_scan

    await run_operating_scan(ctx)
    return await read_operating_brief(ctx, auto_rebuild=False)


async def scan_operating_intelligence(ctx: TenantCtx) -> OperatingBrief:
    """Run the agentic scan over the current operating model."""
    await read_operating_brief(ctx)
    from app.agentic import run_operating_scan

    await run_operating_scan(ctx)
    return await read_operating_brief(ctx, auto_rebuild=False)


async def read_operating_brief(ctx: TenantCtx, *, auto_rebuild: bool = True) -> OperatingBrief:
    async with open_session() as session:
        asset_count = (
            await session.execute(
                select(OperatingAsset.id).where(
                    OperatingAsset.organization_id == ctx.organization_id
                )
            )
        ).all()
        source_count = (
            await session.execute(
                select(DataSource.id).where(DataSource.organization_id == ctx.organization_id)
            )
        ).all()

    if auto_rebuild and source_count and not asset_count:
        return await rebuild_operating_intelligence(ctx)

    if auto_rebuild and asset_count:
        async with open_session() as session:
            sample_asset = (
                await session.execute(
                    select(OperatingAsset)
                    .where(OperatingAsset.organization_id == ctx.organization_id)
                    .limit(1)
                )
            ).scalar_one_or_none()
            needs_scan = sample_asset is not None and not isinstance(
                (sample_asset.profile or {}).get("agentic_role"), dict,
            )
        if needs_scan:
            from app.agentic import run_operating_scan
            await run_operating_scan(ctx)

    async with open_session() as session:
        assets = list(
            (
                await session.execute(
                    select(OperatingAsset)
                    .where(OperatingAsset.organization_id == ctx.organization_id)
                    .order_by(OperatingAsset.source_name.asc(), OperatingAsset.table_label.asc())
                )
            )
            .scalars()
            .all()
        )
        columns = list(
            (
                await session.execute(
                    select(OperatingColumn)
                    .where(OperatingColumn.organization_id == ctx.organization_id)
                    .order_by(OperatingColumn.name.asc())
                )
            )
            .scalars()
            .all()
        )
        relationships = list(
            (
                await session.execute(
                    select(OperatingRelationship)
                    .where(OperatingRelationship.organization_id == ctx.organization_id)
                    .order_by(OperatingRelationship.confidence.desc())
                    .limit(50)
                )
            )
            .scalars()
            .all()
        )
        metrics = list(
            (
                await session.execute(
                    select(MetricDefinition)
                    .where(MetricDefinition.organization_id == ctx.organization_id)
                    .order_by(MetricDefinition.status.asc(), MetricDefinition.name.asc())
                )
            )
            .scalars()
            .all()
        )
        values = list(
            (
                await session.execute(
                    select(MetricValue)
                    .where(MetricValue.organization_id == ctx.organization_id)
                    .order_by(MetricValue.computed_at.desc())
                )
            )
            .scalars()
            .all()
        )
        insights = list(
            (
                await session.execute(
                    select(Insight)
                    .where(Insight.organization_id == ctx.organization_id)
                    .order_by(Insight.detected_at.desc())
                    .limit(50)
                )
            )
            .scalars()
            .all()
        )
        memories = list(
            (
                await session.execute(
                    select(BusinessMemory)
                    .where(
                        BusinessMemory.organization_id == ctx.organization_id,
                        BusinessMemory.status == "active",
                    )
                    .order_by(BusinessMemory.updated_at.desc())
                    .limit(50)
                )
            )
            .scalars()
            .all()
        )
        actions = list(
            (
                await session.execute(
                    select(ActionProposal)
                    .where(ActionProposal.organization_id == ctx.organization_id)
                    .order_by(ActionProposal.created_at.desc())
                    .limit(50)
                )
            )
            .scalars()
            .all()
        )

    columns_by_asset: dict[UUID, list[OperatingColumn]] = {}
    for col in columns:
        columns_by_asset.setdefault(col.asset_id, []).append(col)

    latest_value_by_metric: dict[UUID, MetricValue] = {}
    for value in values:
        latest_value_by_metric.setdefault(value.metric_id, value)

    actions_by_insight: dict[UUID, list[ActionProposal]] = {}
    for action in actions:
        if action.insight_id is not None:
            actions_by_insight.setdefault(action.insight_id, []).append(action)

    asset_label_by_id = {asset.id: asset.table_label for asset in assets}
    asset_qname_by_id = {asset.id: asset.qualified_name for asset in assets}

    last_built_at = max(
        (asset.last_profiled_at for asset in assets if asset.last_profiled_at),
        default=None,
    )
    business = await _build_business_view(
        ctx,
        assets=assets,
        relationships=relationships,
        asset_label_by_id=asset_label_by_id,
        asset_qname_by_id=asset_qname_by_id,
        insights=insights,
        actions=actions,
        metrics=metrics,
        columns_by_asset=columns_by_asset,
        memories=memories,
    )

    return OperatingBrief(
        summary=OperatingSummary(
            assets=len(assets),
            columns=len(columns),
            relationships=len(relationships),
            metrics=len(metrics),
            open_insights=len([i for i in insights if i.status == "open"]),
            proposed_actions=len([a for a in actions if a.status == "proposed"]),
            memories=len(memories),
            last_built_at=last_built_at.isoformat() if last_built_at else None,
        ),
        business=business,
        assets=[
            {
                "id": str(asset.id),
                "qualified_name": asset.qualified_name,
                "source_name": asset.source_name,
                "table_label": asset.table_label,
                "row_count": asset.row_count,
                "column_count": asset.column_count,
                "status": asset.status,
                "profile": asset.profile,
                "last_profiled_at": (
                    asset.last_profiled_at.isoformat()
                    if asset.last_profiled_at
                    else None
                ),
                "columns": [
                    {
                        "id": str(col.id),
                        "name": col.name,
                        "observed_type": col.observed_type,
                        "semantic_type": col.semantic_type,
                        "null_rate": col.null_rate,
                        "unique_count": col.unique_count,
                        "confidence": col.confidence,
                        "sample_values": col.sample_values,
                        "profile": col.profile,
                    }
                    for col in columns_by_asset.get(asset.id, [])
                ],
            }
            for asset in assets
        ],
        relationships=[
            {
                "id": str(rel.id),
                "left_asset_id": str(rel.left_asset_id),
                "left_asset": asset_label_by_id.get(rel.left_asset_id),
                "left_qualified_name": asset_qname_by_id.get(rel.left_asset_id),
                "left_column": rel.left_column,
                "right_asset_id": str(rel.right_asset_id),
                "right_asset": asset_label_by_id.get(rel.right_asset_id),
                "right_qualified_name": asset_qname_by_id.get(rel.right_asset_id),
                "right_column": rel.right_column,
                "relationship_kind": rel.relationship_kind,
                "status": rel.status,
                "confidence": rel.confidence,
                "evidence": rel.evidence,
            }
            for rel in relationships
        ],
        metrics=[
            {
                "id": str(metric.id),
                "key": metric.key,
                "name": metric.name,
                "description": metric.description,
                "metric_type": metric.metric_type,
                "status": metric.status,
                "confidence": metric.confidence,
                "grain": metric.grain,
                "definition": metric.definition,
                "latest_value": (
                    latest_value_by_metric[metric.id].value
                    if metric.id in latest_value_by_metric
                    else None
                ),
                "latest_computed_at": (
                    latest_value_by_metric[metric.id].computed_at.isoformat()
                    if metric.id in latest_value_by_metric
                    else None
                ),
            }
            for metric in metrics
        ],
        insights=[
            {
                "id": str(insight.id),
                "kind": insight.kind,
                "title": insight.title,
                "summary": insight.summary,
                "severity": insight.severity,
                "status": insight.status,
                "confidence": insight.confidence,
                "impact_score": insight.impact_score,
                "evidence": insight.evidence,
                "why": insight.evidence.get("why"),
                "analysis_graph": insight.evidence.get("analysis_graph"),
                "result_preview": insight.evidence.get("result_preview") or [],
                "audience_spec": insight.evidence.get("audience_spec") or {},
                "lineage": insight.evidence.get("lineage") or [],
                "interpretation": insight.evidence.get("interpretation") or {},
                "tags": insight.evidence.get("tags") or [],
                "chart_specs": insight.evidence.get("chart_specs") or [],
                "actions": [
                    {
                        "id": str(action.id),
                        "kind": action.kind,
                        "title": action.title,
                        "summary": action.summary,
                        "status": action.status,
                        "why": action.proposed_payload.get("why"),
                        "action_type": action.proposed_payload.get("action_type", action.kind),
                        "capability_required": action.proposed_payload.get("capability_required"),
                        "execution_mode": action.proposed_payload.get("execution_mode"),
                        "payload": action.proposed_payload.get("payload") or {},
                        "approval_scope": action.approval_scope,
                        "risk": action.proposed_payload.get("risk"),
                    }
                    for action in actions_by_insight.get(insight.id, [])
                ],
                "source": insight.source,
                "detected_at": insight.detected_at.isoformat(),
                "dismissed_at": (
                    insight.dismissed_at.isoformat() if insight.dismissed_at else None
                ),
            }
            for insight in insights
        ],
        memories=[
            {
                "id": str(memory.id),
                "key": memory.key,
                "value": memory.value,
                "source": memory.source,
                "confidence": memory.confidence,
                "last_confirmed_at": (
                    memory.last_confirmed_at.isoformat()
                    if memory.last_confirmed_at
                    else None
                ),
            }
            for memory in memories
        ],
        actions=[
            {
                "id": str(action.id),
                "insight_id": str(action.insight_id) if action.insight_id else None,
                "kind": action.kind,
                "title": action.title,
                "summary": action.summary,
                "status": action.status,
                "why": action.proposed_payload.get("why"),
                "action_type": action.proposed_payload.get("action_type", action.kind),
                "capability_required": action.proposed_payload.get("capability_required"),
                "execution_mode": action.proposed_payload.get("execution_mode"),
                "payload": action.proposed_payload.get("payload") or {},
                "risk": action.proposed_payload.get("risk"),
                "proposed_payload": action.proposed_payload,
                "approval_scope": action.approval_scope,
                "created_by_agent": action.created_by_agent,
                "approved_at": action.approved_at.isoformat() if action.approved_at else None,
                "executed_at": action.executed_at.isoformat() if action.executed_at else None,
            }
            for action in actions
        ],
    )


async def remember(ctx: TenantCtx, body: RememberInput) -> dict[str, Any]:
    now = datetime.now(UTC)
    async with open_session() as session:
        result = await session.execute(
            select(BusinessMemory).where(
                BusinessMemory.organization_id == ctx.organization_id,
                BusinessMemory.key == body.key,
            )
        )
        memory = result.scalar_one_or_none()
        if memory is None:
            memory = BusinessMemory(
                organization_id=ctx.organization_id,
                key=body.key,
                value=body.value,
                source="user",
                status="active",
                confidence=1.0,
                last_confirmed_at=now,
            )
            session.add(memory)
        else:
            memory.value = body.value
            memory.source = "user"
            memory.status = "active"
            memory.confidence = 1.0
            memory.last_confirmed_at = now

        session.add(
            _audit(
                ctx,
                action="business_memory.upsert",
                target_type="business_memory",
                target_id=body.key,
                metadata={"key": body.key},
            )
        )
        await session.flush()
        return {"id": str(memory.id), "key": memory.key, "value": memory.value}


async def dismiss_insight(ctx: TenantCtx, insight_id: UUID) -> dict[str, bool]:
    now = datetime.now(UTC)
    async with open_session() as session:
        insight = await session.get(Insight, insight_id)
        if insight is None or insight.organization_id != ctx.organization_id:
            return {"ok": False}
        insight.status = "dismissed"
        insight.dismissed_at = now
        # Capture the dismissal as a BusinessMemory row so v1.5 agents can
        # learn what the user has consistently said "not this" to. Stored as
        # a JSON value keyed on insight kind + entity so future scans can
        # query "have I dismissed this kind before?" in O(1).
        import json as _json
        ev = insight.evidence if isinstance(insight.evidence, dict) else {}
        team_id = (insight.source or {}).get("team_id") if isinstance(insight.source, dict) else None
        memory_key = f"dismissal:{insight.kind}"[:255]
        existing = (
            await session.execute(
                select(BusinessMemory).where(
                    BusinessMemory.organization_id == ctx.organization_id,
                    BusinessMemory.key == memory_key,
                )
            )
        ).scalar_one_or_none()
        dismissal_record = {
            "insight_id": str(insight_id),
            "kind": insight.kind,
            "team_id": team_id,
            "title": insight.title,
            "tags": ev.get("tags") or [],
            "dismissed_at": now.isoformat(),
        }
        if existing is None:
            session.add(BusinessMemory(
                organization_id=ctx.organization_id,
                key=memory_key,
                value=_json.dumps({"count": 1, "history": [dismissal_record]}),
                source="user",
                status="active",
                confidence=1.0,
                last_confirmed_at=now,
            ))
        else:
            try:
                payload = _json.loads(existing.value) if existing.value else {}
            except Exception:
                payload = {}
            history = list(payload.get("history") or [])
            history.append(dismissal_record)
            payload = {"count": len(history), "history": history[-25:]}
            existing.value = _json.dumps(payload)
            existing.last_confirmed_at = now
        session.add(
            _audit(
                ctx,
                action="insight.dismiss",
                target_type="insight",
                target_id=str(insight_id),
                metadata={"kind": insight.kind, "team_id": team_id},
            )
        )
    return {"ok": True}


async def approve_action(ctx: TenantCtx, action_id: UUID) -> dict[str, bool]:
    now = datetime.now(UTC)
    async with open_session() as session:
        action = await session.get(ActionProposal, action_id)
        if action is None or action.organization_id != ctx.organization_id:
            return {"ok": False}
        action.status = "approved"
        action.approved_at = now
        session.add(
            _audit(
                ctx,
                action="action.approve",
                target_type="action_proposal",
                target_id=str(action_id),
                metadata={"kind": action.kind},
            )
        )
    return {"ok": True}
