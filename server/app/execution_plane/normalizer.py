"""Normalize agent-emitted analysis graphs for execution."""

from __future__ import annotations

from app.analysis_contracts import (
    AggregateOp,
    AnalysisGraphPlan,
    AnalysisOp,
    FilterOp,
    JoinOp,
    LimitOp,
    RankOp,
    SelectOp,
)
from app.execution_plane.contracts import (
    ExecutionCatalog,
    NormalizedExecutionNode,
    NormalizedExecutionPlan,
    PlanValidationError,
)
from app.execution_plane.sql import validate_measure_alias, validate_operator_id


def normalize_analysis_plan(
    plan: AnalysisGraphPlan,
    catalog: ExecutionCatalog,
) -> NormalizedExecutionPlan:
    """Validate graph shape and resolve the execution footprint.

    This step is deliberately SQL-free. It does not choose analyses, joins, or
    fields. It only normalizes the agent-emitted Baseflo query language into an
    internal representation the translator can compile safely.
    """
    if not plan.operators:
        raise PlanValidationError("AnalysisGraphPlan has no operators")

    seen: set[str] = set()
    nodes: list[NormalizedExecutionNode] = []
    source_asset_ids: set[str] = set()
    field_ids: set[str] = set()

    for op in plan.operators:
        validate_operator_id(op.id)
        if op.id in seen:
            raise PlanValidationError("Duplicate operator id", details={"operator_id": op.id})

        inputs = _input_ids(op)
        missing_inputs = [input_id for input_id in inputs if input_id not in seen]
        if missing_inputs:
            raise PlanValidationError(
                "Operator input must reference an earlier operator",
                details={"operator_id": op.id, "missing_inputs": missing_inputs},
            )

        op_asset_ids: list[str] = []
        op_field_ids = _field_ids(op)
        if op.op == "source":
            if op.asset_id not in catalog.assets:
                raise PlanValidationError("Unknown source asset", details={"asset_id": op.asset_id})
            op_asset_ids = [op.asset_id]
            source_asset_ids.add(op.asset_id)

        for field_id in op_field_ids:
            if field_id not in catalog.fields:
                raise PlanValidationError("Unknown field id", details={"field_id": field_id})
            field = catalog.fields[field_id]
            if field.asset_id not in catalog.assets:
                raise PlanValidationError(
                    "Field belongs to an asset that is not in the execution catalog",
                    details={"field_id": field_id, "asset_id": field.asset_id},
                )
            field_ids.add(field_id)

        if op.op == "aggregate":
            for measure in op.measures:
                validate_measure_alias(measure.alias)

        nodes.append(
            NormalizedExecutionNode(
                id=op.id,
                op=op.op,
                inputs=inputs,
                asset_ids=op_asset_ids,
                field_ids=op_field_ids,
            )
        )
        seen.add(op.id)

    if plan.output not in seen:
        raise PlanValidationError("Output operator does not exist", details={"output": plan.output})

    unsourced_fields = sorted(
        field_id
        for field_id in field_ids
        if catalog.fields[field_id].asset_id not in source_asset_ids
    )
    if unsourced_fields:
        raise PlanValidationError(
            "Plan references fields whose assets are not sourced",
            details={"field_ids": unsourced_fields},
        )

    return NormalizedExecutionPlan(
        graph_id=plan.graph_id,
        hypothesis_id=plan.hypothesis_id,
        output=plan.output,
        nodes=nodes,
        source_asset_ids=sorted(source_asset_ids),
        field_ids=sorted(field_ids),
        allowed_storage_tables=sorted(
            catalog.assets[asset_id].storage_table for asset_id in source_asset_ids
        ),
    )


def _input_ids(op: AnalysisOp) -> list[str]:
    if isinstance(op, SelectOp | FilterOp | AggregateOp | RankOp | LimitOp):
        return [op.input]
    if isinstance(op, JoinOp):
        return [op.left_input, op.right_input]
    return []


def _field_ids(op: AnalysisOp) -> list[str]:
    if isinstance(op, SelectOp):
        return list(op.field_ids)
    if isinstance(op, FilterOp):
        return [predicate.field_id for predicate in op.predicates]
    if isinstance(op, JoinOp):
        return [op.left_field_id, op.right_field_id]
    if isinstance(op, AggregateOp):
        field_ids = list(op.group_by_field_ids)
        field_ids.extend(
            measure.field_id
            for measure in op.measures
            if measure.field_id is not None
        )
        return field_ids
    return []
