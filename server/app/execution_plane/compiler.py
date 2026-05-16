"""Compile typed AnalysisGraphPlan operators into safe DuckDB SQL."""

from __future__ import annotations

from app.analysis_contracts import (
    AggregateOp,
    AnalysisGraphPlan,
    FilterOp,
    JoinOp,
    LimitOp,
    RankOp,
    SelectOp,
    SourceOp,
)
from app.execution_plane.contracts import (
    ColumnState,
    CompiledAnalysisPlan,
    ExecutionCatalog,
    NodeState,
    PlanCompileError,
)
from app.execution_plane.guard import render_readonly_select
from app.execution_plane.normalizer import normalize_analysis_plan
from app.execution_plane.sql import (
    column_expr,
    is_numeric_type,
    numeric_expr,
    predicate_sql,
    q,
    unique_alias,
    validate_measure_alias,
)
from app.execution_plane.validator import (
    require_field,
    require_input,
    require_relationship,
)


def compile_analysis_plan(
    plan: AnalysisGraphPlan,
    catalog: ExecutionCatalog,
) -> CompiledAnalysisPlan:
    normalized_plan = normalize_analysis_plan(plan, catalog)
    states: dict[str, NodeState] = {}
    for op in plan.operators:
        if op.op == "source":
            states[op.id] = _compile_source(op, catalog)
        elif op.op == "select":
            states[op.id] = _compile_select(op, states)
        elif op.op == "filter":
            states[op.id] = _compile_filter(op, states)
        elif op.op == "aggregate":
            states[op.id] = _compile_aggregate(op, states)
        elif op.op == "join":
            states[op.id] = _compile_join(op, states, catalog)
        elif op.op == "rank":
            states[op.id] = _compile_rank(op, states)
        elif op.op == "limit":
            states[op.id] = _compile_limit(op, states)
        else:  # pragma: no cover - discriminated union protects this
            raise PlanCompileError(f"Unsupported operator: {op.op}")

    output_state = states.get(plan.output)
    if output_state is None:
        raise PlanCompileError("Output node was not compiled", details={"output": plan.output})
    sql = render_readonly_select(
        f"SELECT * FROM ({output_state.sql}) AS final",
        allowed_tables=set(normalized_plan.allowed_storage_tables),
        stage="analysis_plan",
    )
    return CompiledAnalysisPlan(
        graph_id=plan.graph_id,
        sql=sql,
        output_node=plan.output,
        source_asset_ids=normalized_plan.source_asset_ids,
        source_tables=normalized_plan.allowed_storage_tables,
        field_ids=normalized_plan.field_ids,
        operation_count=normalized_plan.operation_count,
        lineage=output_state.lineage(),
        warnings=[],
    )


def _compile_source(op: SourceOp, catalog: ExecutionCatalog) -> NodeState:
    asset = catalog.assets[op.asset_id]
    fields = [
        field for field in catalog.fields.values()
        if field.asset_id == asset.asset_id and not _is_system_field(field)
    ]
    if not fields:
        raise PlanCompileError("Source asset has no executable fields", details={"asset_id": asset.asset_id})
    used: set[str] = set()
    columns: dict[str, ColumnState] = {}
    field_states: dict[str, ColumnState] = {}
    selects: list[str] = []
    for field in sorted(fields, key=lambda item: item.name):
        alias = unique_alias(field.name, used, salt=field.field_id)
        state = ColumnState(
            alias=alias,
            field_id=field.field_id,
            asset_id=asset.asset_id,
            observed_type=field.observed_type,
            source_name=field.name,
        )
        columns[alias] = state
        field_states[field.field_id] = state
        selects.append(f"{q(field.name)} AS {q(alias)}")
    sql = f"SELECT {', '.join(selects)} FROM {q(asset.storage_table)}"
    return NodeState(sql=sql, columns=columns, fields=field_states)


def _compile_select(op: SelectOp, states: dict[str, NodeState]) -> NodeState:
    source = require_input(states, op.input, op_id=op.id)
    selected_columns: dict[str, ColumnState] = {}
    selected_fields: dict[str, ColumnState] = {}
    selects: list[str] = []
    for field_id in op.field_ids:
        require_field(source, field_id, op_id=op.id)
        column = source.fields[field_id]
        selected_columns[column.alias] = column
        selected_fields[field_id] = column
        selects.append(f"src.{q(column.alias)} AS {q(column.alias)}")
    sql = f"SELECT {', '.join(selects)} FROM ({source.sql}) AS src"
    return NodeState(sql=sql, columns=selected_columns, fields=selected_fields)


def _compile_filter(op: FilterOp, states: dict[str, NodeState]) -> NodeState:
    source = require_input(states, op.input, op_id=op.id)
    predicates: list[str] = []
    for predicate in op.predicates:
        require_field(source, predicate.field_id, op_id=op.id)
        column = source.fields[predicate.field_id]
        predicates.append(
            predicate_sql(
                alias=column.alias,
                observed_type=column.observed_type,
                operator=predicate.operator,
                value=predicate.value,
            )
        )
    where_clause = " AND ".join(predicates) if predicates else "true"
    sql = f"SELECT * FROM ({source.sql}) AS src WHERE {where_clause}"
    return NodeState(sql=sql, columns=dict(source.columns), fields=dict(source.fields))


def _compile_aggregate(op: AggregateOp, states: dict[str, NodeState]) -> NodeState:
    source = require_input(states, op.input, op_id=op.id)
    used: set[str] = set()
    selected_columns: dict[str, ColumnState] = {}
    selected_fields: dict[str, ColumnState] = {}
    select_parts: list[str] = []
    group_exprs: list[str] = []
    for field_id in op.group_by_field_ids:
        require_field(source, field_id, op_id=op.id)
        column = source.fields[field_id]
        selected_columns[column.alias] = column
        selected_fields[field_id] = column
        used.add(column.alias)
        select_parts.append(f"src.{q(column.alias)} AS {q(column.alias)}")
        group_exprs.append(f"src.{q(column.alias)}")

    for measure in op.measures:
        alias = validate_measure_alias(measure.alias)
        if alias in used:
            raise PlanCompileError("Measure alias collides with an existing column", details={"alias": alias})
        used.add(alias)
        expr: str
        observed_type = "number"
        asset_id = None
        source_name = None
        if measure.aggregate == "count" and measure.field_id is None:
            expr = "count(*)"
        else:
            if measure.field_id is None:
                raise PlanCompileError(
                    "Only count may omit field_id",
                    details={"operator_id": op.id, "alias": measure.alias},
                )
            require_field(source, measure.field_id, op_id=op.id)
            column = source.fields[measure.field_id]
            observed_type = column.observed_type
            asset_id = column.asset_id
            source_name = column.source_name
            if measure.aggregate in {"sum", "avg"}:
                if not is_numeric_type(column.observed_type):
                    raise PlanCompileError(
                        "sum/avg requires a numeric profiled field",
                        details={
                            "operator_id": op.id,
                            "field_id": measure.field_id,
                            "observed_type": column.observed_type,
                        },
                    )
                expr = f"{measure.aggregate}({numeric_expr(column.alias)})"
            elif measure.aggregate in {"min", "max"} and is_numeric_type(column.observed_type):
                expr = f"{measure.aggregate}({numeric_expr(column.alias)})"
            else:
                expr = f"{measure.aggregate}({column_expr(column.alias)})"
        state = ColumnState(
            alias=alias,
            field_id=measure.field_id,
            asset_id=asset_id,
            observed_type=observed_type,
            source_name=source_name,
        )
        selected_columns[alias] = state
        select_parts.append(f"{expr} AS {q(alias)}")

    group_clause = f" GROUP BY {', '.join(group_exprs)}" if group_exprs else ""
    sql = f"SELECT {', '.join(select_parts)} FROM ({source.sql}) AS src{group_clause}"
    return NodeState(sql=sql, columns=selected_columns, fields=selected_fields)


def _compile_join(op: JoinOp, states: dict[str, NodeState], catalog: ExecutionCatalog) -> NodeState:
    left = require_input(states, op.left_input, op_id=op.id)
    right = require_input(states, op.right_input, op_id=op.id)
    require_field(left, op.left_field_id, op_id=op.id)
    require_field(right, op.right_field_id, op_id=op.id)
    require_relationship(catalog, op.left_field_id, op.right_field_id, op_id=op.id)

    join_kind = "LEFT JOIN" if op.join_kind == "left" else "INNER JOIN"
    used: set[str] = set()
    columns: dict[str, ColumnState] = {}
    fields: dict[str, ColumnState] = {}
    select_parts: list[str] = []

    for alias, column in left.columns.items():
        output_alias = unique_alias(alias, used, salt=f"left:{alias}")
        new_column = _copy_column(column, alias=output_alias)
        columns[output_alias] = new_column
        if column.field_id:
            fields[column.field_id] = new_column
        select_parts.append(f"l.{q(alias)} AS {q(output_alias)}")

    for alias, column in right.columns.items():
        output_alias = unique_alias(alias, used, salt=f"right:{alias}:{column.field_id or ''}")
        new_column = _copy_column(column, alias=output_alias)
        columns[output_alias] = new_column
        if column.field_id:
            fields[column.field_id] = new_column
        select_parts.append(f"r.{q(alias)} AS {q(output_alias)}")

    left_key = left.fields[op.left_field_id].alias
    right_key = right.fields[op.right_field_id].alias
    sql = (
        f"SELECT {', '.join(select_parts)} "
        f"FROM ({left.sql}) AS l {join_kind} ({right.sql}) AS r "
        f"ON l.{q(left_key)} = r.{q(right_key)}"
    )
    return NodeState(sql=sql, columns=columns, fields=fields)


def _compile_rank(op: RankOp, states: dict[str, NodeState]) -> NodeState:
    source = require_input(states, op.input, op_id=op.id)
    if op.order_by_alias not in source.columns:
        raise PlanCompileError(
            "Rank order_by_alias is not available",
            details={"operator_id": op.id, "order_by_alias": op.order_by_alias},
        )
    used = set(source.columns)
    alias = unique_alias(op.alias, used, salt=op.id)
    direction = op.direction.upper()
    sql = (
        f"SELECT src.*, "
        f"rank() OVER (ORDER BY src.{q(op.order_by_alias)} {direction} NULLS LAST) AS {q(alias)} "
        f"FROM ({source.sql}) AS src"
    )
    columns = dict(source.columns)
    columns[alias] = ColumnState(alias=alias, observed_type="integer", source_name=op.alias)
    return NodeState(sql=sql, columns=columns, fields=dict(source.fields))


def _compile_limit(op: LimitOp, states: dict[str, NodeState]) -> NodeState:
    source = require_input(states, op.input, op_id=op.id)
    sql = f"SELECT * FROM ({source.sql}) AS src LIMIT {op.limit}"
    return NodeState(sql=sql, columns=dict(source.columns), fields=dict(source.fields))


def _copy_column(column: ColumnState, *, alias: str) -> ColumnState:
    return ColumnState(
        alias=alias,
        field_id=column.field_id,
        asset_id=column.asset_id,
        observed_type=column.observed_type,
        source_name=column.source_name,
    )


def _is_system_field(field: object) -> bool:
    profile = getattr(field, "profile", None)
    if isinstance(profile, dict) and profile.get("system_column"):
        return True
    name = getattr(field, "name", "")
    return isinstance(name, str) and name.startswith("_bf_")
