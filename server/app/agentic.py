"""Agentic operating intelligence — contracts + runtime + pipeline.

This module is split into three layers:

1. **Typed contracts** (Pydantic models): the data agents emit and the runtime
   consumes. These never change at runtime.
2. **AnalysisRuntime**: compiles `AnalysisGraph` plans into safe DuckDB SQL
   (via sqlglot validation) and executes them. Deterministic. No semantics.
3. **`run_operating_scan`**: the pipeline. It loads the operating state and
   walks through every capability agent (`app/agents/*`) to produce roles,
   relationships, hypotheses, materialized analyses, interpretations,
   narratives, action drafts, and the Brief synthesis.

Nothing in this module makes a semantic decision. Every "what is this column",
"what's worth investigating", "what should we say", "what should we do"
question is answered by an agent. Templates are not allowed here.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
from difflib import get_close_matches
from datetime import UTC, datetime
from typing import Annotated, Any, Literal
from uuid import UUID

import sqlglot
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import delete, select
from sqlalchemy.orm.attributes import flag_modified

from app.core.context import TenantCtx
from app.core.errors import ValidationError
from app.db.models import (
    ActionProposal,
    AuditEvent,
    BusinessMemory,
    Insight,
    OperatingAsset,
    OperatingColumn,
    OperatingRelationship,
)
from app.db.session import open_session
from app.substrate import safe_query

logger = logging.getLogger("baseflo.agentic")

_GENERATOR = "agentic_operating_intelligence_v2"
_RESULT_LIMIT = 50
_MIN_CONFIDENCE = 0.4


# ============================================================================
# Typed contracts — what agents emit, what the runtime consumes
# ============================================================================


class ContractModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class AssetRole(ContractModel):
    agent: Literal["AssetSemanticist"] = "AssetSemanticist"
    asset_id: str
    qualified_name: str
    role: str
    entity_type: str
    keys: list[str] = Field(default_factory=list)
    time_dim: str | None = None
    measures: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    why: str
    confidence: float = Field(ge=0.0, le=1.0)


class JoinProposal(ContractModel):
    agent: Literal["Reconciler"] = "Reconciler"
    left_asset_id: str
    right_asset_id: str
    left_table: str
    right_table: str
    left_key: str
    right_key: str
    expected_cardinality: str
    confidence: float = Field(ge=0.0, le=1.0)
    why: str


class SignalSpec(ContractModel):
    asset_id: str
    table: str
    measure: str
    aggregate: Literal["sum", "avg", "count", "min", "max"]
    direction: Literal["asc", "desc"]
    role: str


class PatternHypothesis(ContractModel):
    agent: Literal["PatternProposer"] = "PatternProposer"
    pattern_type: str
    target_entity: str
    target_asset_id: str
    signals: list[SignalSpec]
    shape: str
    why: str
    priority: float = Field(ge=0.0, le=1.0)


class SourceNode(ContractModel):
    op: Literal["source"] = "source"
    id: str
    table: str
    # Optional business namespace used by compiler-built graphs. When present,
    # source columns are emitted as stable aliases such as `product__title`.
    namespace: str | None = None


class FilterPredicate(ContractModel):
    column: str
    operator: Literal["=", "!=", ">", ">=", "<", "<=", "is_not_null", "is_null"]
    value: str | float | int | bool | None = None


class FilterNode(ContractModel):
    op: Literal["filter"] = "filter"
    id: str
    input: str
    predicates: list[FilterPredicate]


class AggregateMeasure(ContractModel):
    function: Literal["sum", "avg", "count", "min", "max"]
    column: str | None = None
    alias: str

    @field_validator("alias")
    @classmethod
    def _alias_safe(cls, value: str) -> str:
        _require_safe_identifier(value)
        return value


class AggregateNode(ContractModel):
    op: Literal["aggregate"] = "aggregate"
    id: str
    input: str
    group_by: list[str]
    measures: list[AggregateMeasure]


class RankNode(ContractModel):
    op: Literal["rank"] = "rank"
    id: str
    input: str
    order_by: str
    direction: Literal["asc", "desc"]
    alias: str = "signal_rank"


class LimitNode(ContractModel):
    op: Literal["limit"] = "limit"
    id: str
    input: str
    limit: int = Field(ge=1, le=100)


class ProjectNode(ContractModel):
    op: Literal["project"] = "project"
    id: str
    input: str
    columns: list[str]


class JoinNode(ContractModel):
    """Inner-join two upstream nodes on a single column pair.

    Both sides must already be SELECT-shaped subqueries (from `source`,
    `filter`, `aggregate`, etc.). The join column must exist in each side.
    """

    op: Literal["join"] = "join"
    id: str
    left_input: str
    right_input: str
    left_key: str
    right_key: str
    join_kind: Literal["inner", "left"] = "inner"
    # Columns to project from each side after the join. When None, project the
    # full known schema from that side. Collisions are rejected; compiler-built
    # graphs avoid collisions by using business namespaces.
    project_left: list[str] | None = None
    project_right: list[str] | None = None


AnalysisNode = Annotated[
    SourceNode | FilterNode | AggregateNode | RankNode | LimitNode | ProjectNode | JoinNode,
    Field(discriminator="op"),
]


class AnalysisGraph(ContractModel):
    agent: Literal["Instantiator"] = "Instantiator"
    graph_id: str
    hypothesis_type: str
    nodes: list[AnalysisNode]
    output_node: str
    lineage: list[dict[str, str]] = Field(default_factory=list)
    why: str

    @field_validator("nodes")
    @classmethod
    def _has_source(cls, value: list[AnalysisNode]) -> list[AnalysisNode]:
        if not any(node.op == "source" for node in value):
            raise ValueError("AnalysisGraph requires at least one source node")
        return value


class AnalysisResult(ContractModel):
    graph_id: str
    rows: list[dict[str, Any]]
    row_count: int
    result_preview: list[dict[str, Any]]
    audience_spec: dict[str, Any]
    lineage: list[dict[str, Any]]


class Interpretation(ContractModel):
    agent: Literal["Hypothesizer"] = "Hypothesizer"
    claim: str
    why: str
    causal_candidates: list[str] = Field(default_factory=list)
    evidence_refs: list[str] = Field(default_factory=list)
    confidence: float = Field(ge=0.0, le=1.0)


class ActionDraft(ContractModel):
    agent: Literal["ActionDrafter"] = "ActionDrafter"
    action_type: str
    title: str
    summary: str
    why: str
    capability_required: str
    execution_mode: Literal[
        "draft_only",
        "prepare_for_user",
        "delegate_inside_baseflo",
        "adapter_executable",
        "manual_external",
    ]
    payload: dict[str, Any] = Field(default_factory=dict)
    approval_scope: dict[str, Any] = Field(default_factory=dict)
    risk: str


class ChartSpec(ContractModel):
    agent: Literal["ChartSpecAgent"] = "ChartSpecAgent"
    viz_type: Literal["bar", "table", "line", "scatter", "metric"]
    title: str
    why: str
    x: str | None = None
    y: str | None = None
    data_ref: str
    caption: str


class NarrativeSpec(ContractModel):
    agent: Literal["Narrator"] = "Narrator"
    headline: str
    summary: str
    why: str
    style: Literal["brief", "inbox", "ask"] = "brief"


# ============================================================================
# Identifier safety + SQL helpers (deterministic, no semantics)
# ============================================================================


def _require_safe_identifier(value: str) -> None:
    if not value or not all(ch.isalnum() or ch == "_" for ch in value):
        raise ValidationError(
            message=f"Unsafe identifier in analysis graph: {value}",
            code="UNSAFE_ANALYSIS_IDENTIFIER",
            status_hint=400,
        )


def _quote_ident(value: str) -> str:
    _require_safe_identifier(value)
    return '"' + value.replace('"', '""') + '"'


def _slug(value: str) -> str:
    safe = "".join(ch.lower() if ch.isalnum() else "_" for ch in value)
    return "_".join(part for part in safe.split("_") if part)[:80] or "field"


def _analysis_alias(namespace: str, column: str) -> str:
    return f"{_slug(namespace)}__{_slug(column)}"


def _literal_sql(value: str | float | int | bool | None) -> str:
    if value is None:
        return "NULL"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int | float):
        return str(value)
    return "'" + value.replace("'", "''") + "'"


# ============================================================================
# Snapshot loader
# ============================================================================


class _OperatingSnapshot(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    assets: list[OperatingAsset]
    columns_by_asset: dict[UUID, list[OperatingColumn]]
    relationships: list[OperatingRelationship]
    memories: list[BusinessMemory]


async def _load_snapshot(ctx: TenantCtx) -> _OperatingSnapshot:
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
        memories = list(
            (
                await session.execute(
                    select(BusinessMemory).where(
                        BusinessMemory.organization_id == ctx.organization_id,
                        BusinessMemory.status == "active",
                    )
                )
            )
            .scalars()
            .all()
        )

    columns_by_asset: dict[UUID, list[OperatingColumn]] = {}
    for column in columns:
        columns_by_asset.setdefault(column.asset_id, []).append(column)
    return _OperatingSnapshot(
        assets=assets,
        columns_by_asset=columns_by_asset,
        relationships=relationships,
        memories=memories,
    )


# ============================================================================
# AnalysisRuntime — compiles a typed AnalysisGraph into safe DuckDB SQL
# ============================================================================


class AnalysisRuntime:
    """Compile typed AnalysisGraph plans into DuckDB SQL and execute them.

    The runtime is the only thing that builds SQL. Agents emit the typed graph;
    the runtime translates and runs. After string assembly, every plan is
    parsed by sqlglot in the DuckDB dialect — if sqlglot can't parse it,
    the plan is rejected before it hits the database.
    """

    def __init__(
        self,
        *,
        assets: list[OperatingAsset],
        columns_by_asset: dict[UUID, list[OperatingColumn]],
    ):
        self._tables = {asset.qualified_name: asset for asset in assets}
        self._columns_by_table = {
            asset.qualified_name: {column.name for column in columns_by_asset[asset.id]}
            if asset.id in columns_by_asset and columns_by_asset[asset.id]
            else None
            for asset in assets
        }

    def compile(self, graph: AnalysisGraph) -> str:
        node_sql: dict[str, str] = {}
        node_schema: dict[str, list[str] | None] = {}
        for node in graph.nodes:
            if node.op == "source":
                if node.table not in self._tables:
                    raise ValidationError(
                        message=f"Unknown analysis table: {node.table}",
                        code="ANALYSIS_TABLE_UNKNOWN",
                        status_hint=400,
                    )
                known_columns = self._columns_by_table.get(node.table)
                if node.namespace:
                    if known_columns is None:
                        raise ValidationError(
                            message=f"Cannot namespace source {node.table}: no column profile is available.",
                            code="ANALYSIS_SOURCE_SCHEMA_UNKNOWN",
                            status_hint=400,
                        )
                    aliases = [
                        (_analysis_alias(node.namespace, column), column)
                        for column in sorted(known_columns)
                    ]
                    output_columns = [alias for alias, _ in aliases]
                    if len(output_columns) != len(set(output_columns)):
                        raise ValidationError(
                            message=f"Source namespace {node.namespace} creates duplicate field aliases.",
                            code="ANALYSIS_SOURCE_ALIAS_COLLISION",
                            status_hint=400,
                        )
                    select_list = ", ".join(
                        f"{_quote_ident(column)} AS {_quote_ident(alias)}"
                        for alias, column in aliases
                    )
                    node_sql[node.id] = f"SELECT {select_list} FROM {_quote_ident(node.table)}"
                    node_schema[node.id] = output_columns
                elif known_columns is None:
                    node_sql[node.id] = f"SELECT * FROM {_quote_ident(node.table)}"
                    node_schema[node.id] = None
                else:
                    output_columns = sorted(known_columns)
                    select_list = ", ".join(_quote_ident(column) for column in output_columns)
                    node_sql[node.id] = f"SELECT {select_list} FROM {_quote_ident(node.table)}"
                    node_schema[node.id] = output_columns
            elif node.op == "filter":
                source_sql = self._node_sql(node.input, node_sql)
                source_schema = self._node_schema(node.input, node_schema)
                predicates: list[str] = []
                for predicate in node.predicates:
                    _require_safe_identifier(predicate.column)
                    self._require_visible_column(predicate.column, source_schema, purpose="filter")
                    col = _quote_ident(predicate.column)
                    comparable = (
                        f"try_cast({col} AS DOUBLE)"
                        if isinstance(predicate.value, int | float) and not isinstance(predicate.value, bool)
                        else col
                    )
                    if predicate.operator == "is_null":
                        predicates.append(f"{col} IS NULL")
                    elif predicate.operator == "is_not_null":
                        predicates.append(f"{col} IS NOT NULL")
                    else:
                        predicates.append(
                            f"{comparable} {predicate.operator} {_literal_sql(predicate.value)}"
                        )
                where = " AND ".join(predicates) or "1 = 1"
                node_sql[node.id] = f"SELECT * FROM ({source_sql}) AS src WHERE {where}"
                node_schema[node.id] = source_schema
            elif node.op == "aggregate":
                source_sql = self._node_sql(node.input, node_sql)
                source_schema = self._node_schema(node.input, node_schema)
                for column in node.group_by:
                    _require_safe_identifier(column)
                    self._require_visible_column(column, source_schema, purpose="aggregate group_by")
                group_cols = [_quote_ident(column) for column in node.group_by]
                if not group_cols:
                    raise ValidationError(
                        message="Aggregate must group by at least one column.",
                        code="ANALYSIS_AGGREGATE_NO_GROUP",
                        status_hint=400,
                    )
                selects: list[str] = [*group_cols]
                for measure in node.measures:
                    if measure.function == "count" and measure.column is None:
                        expr = "count(*)"
                    else:
                        if measure.column is None:
                            raise ValidationError(
                                message="Non-count aggregate requires a column.",
                                code="ANALYSIS_AGGREGATE_COLUMN_REQUIRED",
                                status_hint=400,
                            )
                        _require_safe_identifier(measure.column)
                        self._require_visible_column(
                            measure.column,
                            source_schema,
                            purpose=f"{measure.function} measure",
                        )
                        expr = (
                            f"{measure.function}(try_cast({_quote_ident(measure.column)} AS DOUBLE))"
                        )
                    _require_safe_identifier(measure.alias)
                    selects.append(f"{expr} AS {_quote_ident(measure.alias)}")
                group_by = ", ".join(group_cols)
                node_sql[node.id] = (
                    f"SELECT {', '.join(selects)} FROM ({source_sql}) AS src "
                    f"WHERE {group_cols[0]} IS NOT NULL GROUP BY {group_by}"
                )
                node_schema[node.id] = [*node.group_by, *[m.alias for m in node.measures]]
            elif node.op == "rank":
                source_sql = self._node_sql(node.input, node_sql)
                source_schema = self._node_schema(node.input, node_schema)
                _require_safe_identifier(node.order_by)
                _require_safe_identifier(node.alias)
                self._require_visible_column(node.order_by, source_schema, purpose="rank")
                node_sql[node.id] = (
                    "SELECT *, rank() OVER (ORDER BY "
                    f"{_quote_ident(node.order_by)} {node.direction.upper()} NULLS LAST) "
                    f"AS {_quote_ident(node.alias)} FROM ({source_sql}) AS src"
                )
                node_schema[node.id] = None if source_schema is None else [*source_schema, node.alias]
            elif node.op == "limit":
                source_sql = self._node_sql(node.input, node_sql)
                node_sql[node.id] = f"SELECT * FROM ({source_sql}) AS src LIMIT {node.limit}"
                node_schema[node.id] = self._node_schema(node.input, node_schema)
            elif node.op == "project":
                source_sql = self._node_sql(node.input, node_sql)
                source_schema = self._node_schema(node.input, node_schema)
                for column in node.columns:
                    _require_safe_identifier(column)
                    self._require_visible_column(column, source_schema, purpose="project")
                columns = ", ".join(_quote_ident(column) for column in node.columns)
                node_sql[node.id] = f"SELECT {columns} FROM ({source_sql}) AS src"
                node_schema[node.id] = list(node.columns)
            elif node.op == "join":
                left_sql = self._node_sql(node.left_input, node_sql)
                right_sql = self._node_sql(node.right_input, node_sql)
                left_schema = self._node_schema(node.left_input, node_schema)
                right_schema = self._node_schema(node.right_input, node_schema)
                _require_safe_identifier(node.left_key)
                _require_safe_identifier(node.right_key)
                self._require_visible_column(node.left_key, left_schema, purpose="join left key")
                self._require_visible_column(node.right_key, right_schema, purpose="join right key")
                left_proj = node.project_left
                right_proj = node.project_right
                if left_schema is not None:
                    left_columns = list(left_schema) if left_proj is None else list(left_proj)
                    for column in left_columns:
                        _require_safe_identifier(column)
                        self._require_visible_column(column, left_schema, purpose="join left projection")
                else:
                    left_columns = left_proj
                if right_schema is not None:
                    right_columns = list(right_schema) if right_proj is None else list(right_proj)
                    for column in right_columns:
                        _require_safe_identifier(column)
                        self._require_visible_column(column, right_schema, purpose="join right projection")
                else:
                    right_columns = right_proj

                if left_columns is not None and right_columns is not None:
                    collisions = set(left_columns) & set(right_columns)
                    if collisions:
                        raise ValidationError(
                            message="Join output column collision: "
                            + ", ".join(sorted(collisions)[:8]),
                            code="ANALYSIS_JOIN_COLUMN_COLLISION",
                            status_hint=400,
                        )
                    parts = [
                        f"lhs.{_quote_ident(column)} AS {_quote_ident(column)}"
                        for column in left_columns
                    ]
                    parts.extend(
                        f"rhs.{_quote_ident(column)} AS {_quote_ident(column)}"
                        for column in right_columns
                    )
                    select_list = ", ".join(parts)
                    node_schema[node.id] = [*left_columns, *right_columns]
                else:
                    select_list = "lhs.*, rhs.*"
                    node_schema[node.id] = None
                kind = "INNER JOIN" if node.join_kind == "inner" else "LEFT JOIN"
                node_sql[node.id] = (
                    f"SELECT {select_list} FROM ({left_sql}) AS lhs "
                    f"{kind} ({right_sql}) AS rhs "
                    f"ON lhs.{_quote_ident(node.left_key)} = rhs.{_quote_ident(node.right_key)}"
                )
            else:
                raise ValidationError(
                    message=f"Unsupported analysis node: {node}",
                    code="ANALYSIS_NODE_UNSUPPORTED",
                    status_hint=400,
                )

        sql = self._node_sql(graph.output_node, node_sql)

        # sqlglot parse round-trip validates the final SQL in DuckDB dialect
        # and gives a normalized form for the audit log.
        try:
            parsed = sqlglot.parse_one(sql, read="duckdb")
            sql = parsed.sql(dialect="duckdb")
        except Exception as exc:
            raise ValidationError(
                message=f"Generated SQL failed sqlglot validation: {exc}",
                code="ANALYSIS_SQL_INVALID",
                status_hint=400,
            ) from exc

        return sql

    @staticmethod
    def _node_sql(node_id: str, node_sql: dict[str, str]) -> str:
        try:
            return node_sql[node_id]
        except KeyError as exc:
            raise ValidationError(
                message=f"Analysis graph references unknown node: {node_id}",
                code="ANALYSIS_NODE_UNKNOWN",
                status_hint=400,
            ) from exc

    @staticmethod
    def _node_schema(
        node_id: str,
        node_schema: dict[str, list[str] | None],
    ) -> list[str] | None:
        try:
            return node_schema[node_id]
        except KeyError as exc:
            raise ValidationError(
                message=f"Analysis graph references unknown node: {node_id}",
                code="ANALYSIS_NODE_UNKNOWN",
                status_hint=400,
            ) from exc

    @staticmethod
    def _require_visible_column(
        column: str,
        schema: list[str] | None,
        *,
        purpose: str,
    ) -> None:
        if schema is None or column in schema:
            return
        matches = get_close_matches(column, schema, n=6)
        candidates = matches or sorted(schema)[:8]
        suffix = f" Candidates: {', '.join(candidates)}." if candidates else ""
        raise ValidationError(
            message=f"Unknown {purpose} column: {column}.{suffix}",
            code="ANALYSIS_COLUMN_UNKNOWN",
            status_hint=400,
        )

    async def execute(self, ctx: TenantCtx, graph: AnalysisGraph) -> AnalysisResult:
        sql = self.compile(graph)
        rows = await asyncio.to_thread(
            safe_query,
            ctx.organization_id,
            sql,
            max_rows=_RESULT_LIMIT,
        )
        preview = rows[:12]
        return AnalysisResult(
            graph_id=graph.graph_id,
            rows=rows,
            row_count=len(rows),
            result_preview=preview,
            audience_spec={
                "type": "analysis_result_rows",
                "graph_id": graph.graph_id,
                "row_count": len(rows),
                "compiled_sql": sql,
            },
            lineage=[*graph.lineage, {"runtime": "AnalysisRuntime", "graph_id": graph.graph_id}],
        )


# ============================================================================
# Pipeline — calls every capability agent in order
# ============================================================================


def _starter_insight(ctx: TenantCtx, *, now: datetime, title: str, summary: str) -> Insight:
    return Insight(
        organization_id=ctx.organization_id,
        kind="starter",
        title=title[:255],
        summary=summary,
        severity="info",
        status="open",
        confidence=1.0,
        impact_score=0.3,
        evidence={"why": summary, "tags": ["setup"], "generator": _GENERATOR},
        source={"type": "agentic_scan"},
        detected_at=now,
    )


def _known_measure_column(
    value: str | None,
    columns_by_table: dict[str, set[str]],
) -> bool:
    if not value or "." not in value:
        return False
    table, column = value.rsplit(".", 1)
    return column in columns_by_table.get(table, set())


def _sanitize_business_model(
    business_model: Any,
    *,
    assets: list[OperatingAsset],
    columns_by_asset: dict[UUID, list[OperatingColumn]],
) -> Any:
    """Ground BusinessModel asset/column references to the connected schema."""
    asset_names = {asset.qualified_name for asset in assets}
    asset_by_id = {asset.id: asset.qualified_name for asset in assets}
    columns_by_table = {
        asset_by_id[asset_id]: {column.name for column in columns}
        for asset_id, columns in columns_by_asset.items()
        if asset_id in asset_by_id
    }
    changed = False

    entities = []
    for entity in business_model.entities:
        related = [name for name in entity.related_assets if name in asset_names]
        primary = entity.primary_asset if entity.primary_asset in asset_names else None
        if primary is None and related:
            primary = related[0]
        if primary is None:
            changed = True
            continue
        if primary != entity.primary_asset or related != entity.related_assets:
            changed = True
        entities.append(entity.model_copy(update={
            "primary_asset": primary,
            "related_assets": related,
        }))

    kpis = []
    for kpi in business_model.primary_kpis:
        measure_column = kpi.measure_column
        if measure_column is not None and not _known_measure_column(measure_column, columns_by_table):
            measure_column = None
            changed = True
        derived_from = [name for name in kpi.derived_from if name in asset_names]
        if derived_from != kpi.derived_from:
            changed = True
        kpis.append(kpi.model_copy(update={
            "measure_column": measure_column,
            "derived_from": derived_from,
        }))

    if not changed:
        return business_model
    return business_model.model_copy(update={
        "entities": entities,
        "primary_kpis": kpis,
        "confidence": min(business_model.confidence, 0.65),
    })


def _sanitize_asset_role(
    role: AssetRole,
    *,
    asset: OperatingAsset,
    columns: list[OperatingColumn],
    business_model: dict[str, Any],
) -> AssetRole:
    """Keep agent-emitted role metadata grounded to the exact asset schema."""
    column_names = {column.name for column in columns}
    entity_names = {
        str(entity.get("name"))
        for entity in business_model.get("entities", [])
        if isinstance(entity, dict) and entity.get("name")
    }
    keys = list(dict.fromkeys(key for key in role.keys if key in column_names))
    measures = list(dict.fromkeys(measure for measure in role.measures if measure in column_names))
    time_dim = role.time_dim if role.time_dim in column_names else None
    entity_type = role.entity_type if role.entity_type in entity_names else "unknown"
    changed = (
        keys != role.keys
        or measures != role.measures
        or time_dim != role.time_dim
        or entity_type != role.entity_type
        or role.qualified_name != asset.qualified_name
        or role.asset_id != str(asset.id)
    )
    return role.model_copy(update={
        "asset_id": str(asset.id),
        "qualified_name": asset.qualified_name,
        "entity_type": entity_type,
        "keys": keys,
        "time_dim": time_dim,
        "measures": measures,
        "confidence": min(role.confidence, 0.6) if changed else role.confidence,
    })


async def _upsert_memory(
    ctx: TenantCtx,
    *,
    key: str,
    value: str,
    now: datetime,
    confidence: float = 0.9,
) -> None:
    async with open_session() as session:
        existing = (
            await session.execute(
                select(BusinessMemory).where(
                    BusinessMemory.organization_id == ctx.organization_id,
                    BusinessMemory.key == key,
                )
            )
        ).scalar_one_or_none()
        if existing is None:
            session.add(BusinessMemory(
                organization_id=ctx.organization_id,
                key=key,
                value=value,
                source="agent",
                status="active",
                confidence=confidence,
                last_confirmed_at=now,
            ))
        else:
            existing.value = value
            existing.source = "agent"
            existing.status = "active"
            existing.confidence = confidence
            existing.last_confirmed_at = now


async def run_operating_scan(ctx: TenantCtx) -> dict[str, Any]:
    """The agentic operating-intelligence DAG.

    Phases:
      1.  BusinessUnderstander            (1 agent call)
      2a. AssetSemanticist × N            (parallel)
      3.  RelationshipGraphBuilder        (1 agent call)
      4.  GraphValidator                  (runtime, sample joins)
      5.  FormulaPlanner × ACTIVE_TEAMS   (parallel)
      6.  FormulaCompiler × M             (runtime, sqlglot)
      7.  AnalysisRuntime × M             (parallel SQL)
      8a. Hypothesizer                   (interpret rows)
      8b. Narrator                       (surface prose)
      8c. ActionDrafter                  (action drafts)
      9.  CrossTeamSynthesizer            (1 agent call)
     10.  BriefSynthesizer                (1 agent call)

    Every node emits typed Pydantic. The runtime never makes a semantic
    decision. Agents never write SQL — they emit FormulaSpec, the compiler
    turns it into an AnalysisGraph, the runtime executes it.
    """
    from app.agents import (
        ACTIVE_TEAMS,
        AgentRunError,
        FormulaCompileError,
        agent_is_configured,
        annotate_asset,
        compile_formula,
        draft_actions,
        field_catalog_for_prompt,
        interpret_result,
        map_relationships,
        narrate_interpretation,
        run_team,
        synthesize_brief,
        synthesize_cross_team,
        understand_business,
        validate_graph,
    )
    from app.agents._context import (
        asset_block,
        asset_summary,
        memory_block,
        relationship_candidates_block,
    )

    now = datetime.now(UTC)
    snapshot = await _load_snapshot(ctx)

    # Wipe non-dismissed insights / unapproved actions before a fresh scan.
    async with open_session() as session:
        await session.execute(
            delete(ActionProposal).where(
                ActionProposal.organization_id == ctx.organization_id,
                ActionProposal.executed_at.is_(None),
                ActionProposal.status != "approved",
            )
        )
        await session.execute(
            delete(Insight).where(
                Insight.organization_id == ctx.organization_id,
                Insight.status != "dismissed",
            )
        )

    if not snapshot.assets:
        async with open_session() as session:
            session.add(_starter_insight(
                ctx, now=now,
                title="Connect a source to start",
                summary="Baseflo reads your data once you connect a source like Shopify or a Google Sheet.",
            ))
        return {"insights": 1, "actions": 0, "phase": "no_assets"}

    if not agent_is_configured():
        async with open_session() as session:
            session.add(_starter_insight(
                ctx, now=now,
                title="Operator key needed",
                summary=(
                    "Baseflo can read your data but needs an OpenAI key to narrate findings. "
                    "Set OPENAI_API_KEY in the server environment and refresh."
                ),
            ))
        return {"insights": 1, "actions": 0, "phase": "no_llm"}

    # ----- Shared context -----------------------------------------------------
    user_memories = memory_block(snapshot.memories)
    asset_label_by_id = {asset.id: asset.table_label for asset in snapshot.assets}
    asset_qname_by_id = {asset.id: asset.qualified_name for asset in snapshot.assets}
    sync_failures = [
        {"qualified_name": asset.qualified_name, "table_label": asset.table_label, "status": asset.status}
        for asset in snapshot.assets
        if asset.status not in {"active"}
    ]
    assets_overview = [
        asset_block(asset, snapshot.columns_by_asset.get(asset.id, []))
        for asset in snapshot.assets
    ]

    # ----- Phase 1: BusinessUnderstander -------------------------------------
    try:
        business_model = await understand_business(
            assets_overview=assets_overview,
            sync_failures=sync_failures,
            user_memories=user_memories,
        )
    except AgentRunError as exc:
        logger.warning("BusinessUnderstander failed: %s", exc)
        async with open_session() as session:
            session.add(_starter_insight(
                ctx, now=now,
                title="Couldn't read your business",
                summary="The understanding step failed. Check the operator-key configuration or retry.",
            ))
        return {"insights": 1, "actions": 0, "phase": "business_understander_failed"}

    business_model = _sanitize_business_model(
        business_model,
        assets=snapshot.assets,
        columns_by_asset=snapshot.columns_by_asset,
    )
    business_model_payload = business_model.model_dump(mode="json")
    await _upsert_memory(
        ctx,
        key="business_model",
        value=json.dumps(business_model_payload),
        now=now,
        confidence=business_model.confidence,
    )

    # ----- Phase 2a: AssetSemanticist (parallel per asset) -------------------
    role_results = await asyncio.gather(
        *[
            annotate_asset(
                asset,
                snapshot.columns_by_asset.get(asset.id, []),
                business_model=business_model_payload,
            )
            for asset in snapshot.assets
        ],
        return_exceptions=True,
    )
    roles: list[AssetRole] = []
    for asset, res in zip(snapshot.assets, role_results, strict=True):
        if isinstance(res, BaseException):
            logger.warning("AssetSemanticist failed for %s: %s", asset.qualified_name, res)
            continue
        roles.append(_sanitize_asset_role(
            res,
            asset=asset,
            columns=snapshot.columns_by_asset.get(asset.id, []),
            business_model=business_model_payload,
        ))
    role_by_asset_id: dict[str, AssetRole] = {role.asset_id: role for role in roles}

    async with open_session() as session:
        for asset in snapshot.assets:
            role = role_by_asset_id.get(str(asset.id))
            if role is None:
                continue
            persistent = await session.get(OperatingAsset, asset.id)
            if persistent is None:
                continue
            persistent.profile = {
                **(persistent.profile or {}),
                "agentic_role": role.model_dump(mode="json"),
                "role_vocabulary_version": _GENERATOR,
            }
            flag_modified(persistent, "profile")

    asset_summaries: list[dict[str, Any]] = [
        asset_summary(asset, role_by_asset_id.get(str(asset.id)).model_dump(mode="json")
                      if role_by_asset_id.get(str(asset.id)) else None)
        for asset in snapshot.assets
    ]

    # ----- Phase 3: RelationshipGraphBuilder ---------------------------------
    raw_candidates = relationship_candidates_block(
        snapshot.relationships,
        label_by_id=asset_label_by_id,
        qname_by_id=asset_qname_by_id,
    )
    asset_roles_payload = [role.model_dump(mode="json") for role in roles]

    try:
        entity_graph = await map_relationships(
            business_model=business_model_payload,
            asset_roles=asset_roles_payload,
            raw_candidates=raw_candidates,
        )
    except AgentRunError as exc:
        logger.warning("RelationshipGraphBuilder failed: %s", exc)
        from app.agents._contracts import EntityGraph as _EG
        entity_graph = _EG(nodes=[], edges=[], notes=[f"RelationshipGraphBuilder failed: {exc}"])

    # ----- Phase 4: GraphValidator (deterministic) ---------------------------
    entity_graph = await validate_graph(
        ctx.organization_id,
        entity_graph,
        business_model=business_model_payload,
    )
    entity_graph_payload = entity_graph.model_dump(mode="json")
    field_catalog = field_catalog_for_prompt(
        entity_graph,
        assets=snapshot.assets,
        columns_by_asset=snapshot.columns_by_asset,
    )

    # ----- Phase 5: FormulaPlanner × ACTIVE_TEAMS (parallel) -----------------
    team_results = await asyncio.gather(
        *[
            run_team(
                team_id,
                business_model=business_model_payload,
                entity_graph=entity_graph_payload,
                field_catalog=field_catalog,
                asset_roles=asset_roles_payload,
                memories=user_memories,
            )
            for team_id in ACTIVE_TEAMS
        ],
        return_exceptions=True,
    )
    team_plans = []
    for team_id, res in zip(ACTIVE_TEAMS, team_results, strict=True):
        if isinstance(res, BaseException):
            logger.warning("FormulaPlanner %s failed: %s", team_id, res)
            continue
        team_plans.append(res)

    if not team_plans:
        async with open_session() as session:
            session.add(_starter_insight(
                ctx, now=now,
                title="No team had anything to say today",
                summary="Every team agent failed to propose analyses. Check the operator-key or model availability.",
            ))
        return {"insights": 1, "actions": 0, "phase": "no_team_output"}

    runtime = AnalysisRuntime(
        assets=snapshot.assets,
        columns_by_asset=snapshot.columns_by_asset,
    )

    # ----- Phase 6 + 7 + 8: per-formula compile, run, narrate, draft ---------
    async def _process_formula(team_plan, spec) -> dict[str, Any] | None:
        # Phase 6: compile.
        try:
            plan = compile_formula(
                spec,
                entity_graph,
                assets=snapshot.assets,
                columns_by_asset=snapshot.columns_by_asset,
            )
        except FormulaCompileError as exc:
            logger.warning("FormulaCompiler refused %s/%s: %s", team_plan.team_id, spec.formula_id, exc)
            return None
        # Phase 7: execute.
        try:
            result = await runtime.execute(ctx, plan)
        except ValidationError as exc:
            logger.warning("AnalysisRuntime rejected plan %s: %s", plan.graph_id, exc.message)
            return None
        except Exception as exc:
            logger.warning("AnalysisRuntime failed for plan %s: %s", plan.graph_id, exc)
            return None
        if result.row_count == 0:
            return None
        # Phase 8: interpret, narrate, draft action.
        target_role = role_by_asset_id.get(
            next(
                (
                    str(asset.id)
                    for asset in snapshot.assets
                    if asset.qualified_name == _entity_table_lookup(spec.target_entity, entity_graph)
                ),
                "",
            )
        )
        target_role_payload = target_role.model_dump(mode="json") if target_role else {}
        # Hypothesizer must run before Narrator/ActionDrafter because both need
        # the structured interpretation. Every (team, formula) pair already runs
        # in parallel at the outer level via asyncio.gather over _process_formula.
        try:
            interpretation = await interpret_result(
                team_id=team_plan.team_id,
                business_model=business_model_payload,
                formula=spec.model_dump(mode="json"),
                graph=plan.model_dump(mode="json"),
                rows=result.rows,
            )
        except AgentRunError as exc:
            logger.warning("Hypothesizer failed for %s/%s: %s", team_plan.team_id, spec.formula_id, exc)
            return None
        if interpretation.confidence < _MIN_CONFIDENCE:
            return None
        try:
            narrative = await narrate_interpretation(
                team_id=team_plan.team_id,
                business_model=business_model_payload,
                formula=spec.model_dump(mode="json"),
                graph=plan.model_dump(mode="json"),
                interpretation=interpretation.model_dump(mode="json"),
                rows=result.rows,
                style="brief",
            )
        except AgentRunError as exc:
            logger.warning("Narrator failed for %s/%s: %s", team_plan.team_id, spec.formula_id, exc)
            return None
        try:
            actions_batch = await draft_actions(
                team_id=team_plan.team_id,
                business_model=business_model_payload,
                interpretation=interpretation.model_dump(mode="json"),
                asset_role=target_role_payload,
                rows=result.rows,
            )
        except AgentRunError as exc:
            logger.warning("ActionDrafter failed for %s/%s: %s", team_plan.team_id, spec.formula_id, exc)
            actions_batch = None
        return {
            "team_plan": team_plan,
            "formula": spec,
            "plan": plan,
            "result": result,
            "interpretation": interpretation,
            "narrative": narrative,
            "actions": actions_batch.actions if actions_batch else [],
        }

    formula_tasks: list[Any] = []
    for plan in team_plans:
        for spec in plan.formulas:
            formula_tasks.append(_process_formula(plan, spec))

    processed = await asyncio.gather(*formula_tasks)

    # Persist insights + actions.
    created_insights: list[Insight] = []
    team_insight_records: list[dict[str, Any]] = []
    created_actions = 0
    async with open_session() as session:
        for entry in processed:
            if entry is None:
                continue
            team_plan = entry["team_plan"]
            spec = entry["formula"]
            plan = entry["plan"]
            result = entry["result"]
            interpretation = entry["interpretation"]
            narrative = entry["narrative"]
            actions = entry["actions"]

            target_role = role_by_asset_id.get(
                next(
                    (
                        str(asset.id)
                        for asset in snapshot.assets
                        if asset.qualified_name == _entity_table_lookup(spec.target_entity, entity_graph)
                    ),
                    "",
                )
            )
            insight_tags = sorted(
                {*(target_role.tags if target_role else []), spec.target_entity, team_plan.team_id}
            )
            insight = Insight(
                organization_id=ctx.organization_id,
                kind=f"{team_plan.team_id}__{spec.formula_id}"[:60],
                title=narrative.headline[:255],
                summary=narrative.summary,
                severity="warning" if "stock" in insight_tags or "inventory" in insight_tags else "info",
                status="open",
                confidence=interpretation.confidence,
                impact_score=0.7,
                evidence={
                    "why": interpretation.why,
                    "team_id": team_plan.team_id,
                    "formula": spec.model_dump(mode="json"),
                    "analysis_graph": plan.model_dump(mode="json"),
                    "result_preview": result.result_preview,
                    "audience_spec": result.audience_spec,
                    "lineage": result.lineage,
                    "interpretation": interpretation.model_dump(mode="json"),
                    "narrative": narrative.model_dump(mode="json"),
                    "tags": insight_tags,
                    "generator": _GENERATOR,
                },
                source={
                    "type": "agentic_scan",
                    "team_id": team_plan.team_id,
                    "agents": [
                        "BusinessUnderstander",
                        "AssetSemanticist",
                        "RelationshipGraphBuilder",
                        f"FormulaPlanner[{team_plan.team_id}]",
                        "FormulaCompiler",
                        "AnalysisRuntime",
                        "Hypothesizer",
                        "Narrator",
                        "ActionDrafter",
                    ],
                },
                detected_at=now,
            )
            session.add(insight)
            await session.flush()
            created_insights.append(insight)
            team_insight_records.append({
                "insight_id": str(insight.id),
                "team_id": team_plan.team_id,
                "title": insight.title,
                "summary": insight.summary,
                "claim": interpretation.claim,
                "why": interpretation.why,
                "confidence": insight.confidence,
                "impact_score": insight.impact_score,
                "tags": insight_tags,
                "result_preview": result.result_preview,
            })

            for action in actions[:3]:
                action_key = hashlib.sha256(
                    f"{ctx.organization_id}:{plan.graph_id}:{action.action_type}:{now.isoformat()}".encode()
                ).hexdigest()
                session.add(
                    ActionProposal(
                        organization_id=ctx.organization_id,
                        insight_id=insight.id,
                        kind=action.action_type,
                        title=action.title[:255],
                        summary=action.summary,
                        status="proposed",
                        proposed_payload={
                            "why": action.why,
                            "action_type": action.action_type,
                            "capability_required": action.capability_required,
                            "execution_mode": action.execution_mode,
                            "payload": action.payload,
                            "risk": action.risk,
                            "team_id": team_plan.team_id,
                            "source_graph_id": plan.graph_id,
                        },
                        approval_scope=action.approval_scope,
                        idempotency_key=action_key,
                        created_by_agent=f"ActionDrafter[{team_plan.team_id}]",
                    )
                )
                created_actions += 1

    # ----- Phase 9: CrossTeamSynthesizer -------------------------------------
    cross_team_payload: dict[str, Any] = {}
    if team_insight_records:
        try:
            cross_team = await synthesize_cross_team(
                business_model=business_model_payload,
                team_plans=[p.model_dump(mode="json") for p in team_plans],
                team_insights=team_insight_records,
            )
            cross_team_payload = cross_team.model_dump(mode="json")
            await _upsert_memory(
                ctx, key="cross_team_report",
                value=json.dumps(cross_team_payload), now=now,
            )
        except AgentRunError as exc:
            logger.warning("CrossTeamSynthesizer failed: %s", exc)

    # ----- Phase 10: BriefSynthesizer ----------------------------------------
    if team_insight_records:
        # Collect proposed actions for context.
        actions_block: list[dict[str, Any]] = []
        async with open_session() as session:
            proposed = list(
                (
                    await session.execute(
                        select(ActionProposal)
                        .where(
                            ActionProposal.organization_id == ctx.organization_id,
                            ActionProposal.status == "proposed",
                        )
                        .order_by(ActionProposal.created_at.desc())
                        .limit(30)
                    )
                )
                .scalars()
                .all()
            )
            for action in proposed:
                payload = action.proposed_payload if isinstance(action.proposed_payload, dict) else {}
                actions_block.append({
                    "id": str(action.id),
                    "title": action.title,
                    "summary": action.summary,
                    "kind": action.kind,
                    "team_id": payload.get("team_id"),
                })
        try:
            brief = await synthesize_brief(
                business_model=business_model_payload,
                cross_team_report=cross_team_payload,
                team_plans=[p.model_dump(mode="json") for p in team_plans],
                team_insights=team_insight_records,
                action_backlog=actions_block,
            )
            await _upsert_memory(
                ctx, key="founder_brief",
                value=json.dumps(brief.model_dump(mode="json")), now=now,
            )
        except AgentRunError as exc:
            logger.warning("BriefSynthesizer failed: %s", exc)

    async with open_session() as session:
        session.add(
            AuditEvent(
                organization_id=ctx.organization_id,
                actor_user_id=ctx.user_id,
                actor_type="user",
                action="operating_intelligence.scan",
                target_type="organization",
                target_id=str(ctx.organization_id),
                metadata_={
                    "roles": len(roles),
                    "team_plans": len(team_plans),
                    "formulas_proposed": sum(len(p.formulas) for p in team_plans),
                    "insights": len(created_insights),
                    "actions": created_actions,
                    "generator": _GENERATOR,
                },
                occurred_at=now,
            )
        )

    return {
        "roles": len(roles),
        "team_plans": len(team_plans),
        "formulas_proposed": sum(len(p.formulas) for p in team_plans),
        "insights": len(created_insights),
        "actions": created_actions,
    }


def _entity_table_lookup(entity: str, graph: Any) -> str | None:
    """Tiny helper: resolve an entity name to its qualified table via EntityGraph."""
    if not graph or not hasattr(graph, "nodes"):
        return None
    for node in graph.nodes:
        if node.entity == entity:
            return node.asset_qualified_name
    return None
