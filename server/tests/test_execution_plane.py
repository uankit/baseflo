from __future__ import annotations

from contextlib import suppress
from uuid import uuid4

import pytest


def _catalog(*, with_relationship: bool = True):
    from app.execution_plane.contracts import (
        ExecutionCatalog,
        ResolvedAsset,
        ResolvedField,
        ResolvedRelationship,
    )

    relationships = []
    if with_relationship:
        relationships.append(
            ResolvedRelationship(
                left_field_id="customers.id",
                right_field_id="orders.customer_id",
                confidence=0.91,
            )
        )
    return ExecutionCatalog(
        assets={
            "orders": ResolvedAsset(
                asset_id="orders",
                qualified_name="orders",
                storage_table="orders_exec_test",
                label="Orders",
                row_count=3,
            ),
            "customers": ResolvedAsset(
                asset_id="customers",
                qualified_name="customers",
                storage_table="customers_exec_test",
                label="Customers",
                row_count=2,
            ),
        },
        fields={
            "orders.customer_id": ResolvedField(
                field_id="orders.customer_id",
                asset_id="orders",
                name="customer_id",
                observed_type="text",
                storage_type="varchar",
            ),
            "orders.total": ResolvedField(
                field_id="orders.total",
                asset_id="orders",
                name="total",
                observed_type="number",
                storage_type="varchar",
            ),
            "customers.id": ResolvedField(
                field_id="customers.id",
                asset_id="customers",
                name="id",
                observed_type="text",
                storage_type="varchar",
            ),
            "customers.name": ResolvedField(
                field_id="customers.name",
                asset_id="customers",
                name="name",
                observed_type="text",
                storage_type="varchar",
            ),
        },
        relationships=relationships,
    )


def test_compile_aggregate_filter_rank_plan() -> None:
    from app.analysis_contracts import AnalysisGraphPlan
    from app.execution_plane import compile_analysis_plan

    plan = AnalysisGraphPlan.model_validate(
        {
            "graph_id": "top_customers_by_spend",
            "hypothesis_id": "h1",
            "operators": [
                {"op": "source", "id": "orders", "asset_id": "orders"},
                {
                    "op": "filter",
                    "id": "paid_orders",
                    "input": "orders",
                    "predicates": [
                        {"field_id": "orders.total", "operator": ">", "value": 100}
                    ],
                },
                {
                    "op": "aggregate",
                    "id": "by_customer",
                    "input": "paid_orders",
                    "group_by_field_ids": ["orders.customer_id"],
                    "measures": [
                        {
                            "field_id": "orders.total",
                            "aggregate": "sum",
                            "alias": "total_spent",
                        }
                    ],
                },
                {
                    "op": "rank",
                    "id": "ranked",
                    "input": "by_customer",
                    "order_by_alias": "total_spent",
                    "direction": "desc",
                    "alias": "spend_rank",
                },
                {"op": "limit", "id": "top_10", "input": "ranked", "limit": 10},
            ],
            "output": "top_10",
            "why": "Rank customers by spend.",
        }
    )

    compiled = compile_analysis_plan(plan, _catalog())

    sql_lower = compiled.sql.lower()
    assert "try_cast" in sql_lower
    assert "sum(" in sql_lower
    assert "rank() over" in sql_lower
    assert compiled.operation_count == 5
    assert compiled.source_tables == ["orders_exec_test"]
    assert compiled.field_ids == ["orders.customer_id", "orders.total"]
    assert any(line["field_id"] == "orders.total" for line in compiled.lineage)


def test_join_requires_relationship_evidence() -> None:
    from app.analysis_contracts import AnalysisGraphPlan
    from app.execution_plane import PlanValidationError, compile_analysis_plan

    plan = AnalysisGraphPlan.model_validate(
        {
            "graph_id": "orders_with_customers",
            "hypothesis_id": "h2",
            "operators": [
                {"op": "source", "id": "customers", "asset_id": "customers"},
                {"op": "source", "id": "orders", "asset_id": "orders"},
                {
                    "op": "join",
                    "id": "joined",
                    "left_input": "customers",
                    "right_input": "orders",
                    "left_field_id": "customers.id",
                    "right_field_id": "orders.customer_id",
                },
            ],
            "output": "joined",
            "why": "Join customers to orders.",
        }
    )

    with pytest.raises(PlanValidationError):
        compile_analysis_plan(plan, _catalog(with_relationship=False))

    compiled = compile_analysis_plan(plan, _catalog(with_relationship=True))
    assert "INNER JOIN" in compiled.sql


def test_normalized_plan_requires_inputs_to_reference_earlier_nodes() -> None:
    from app.analysis_contracts import AnalysisGraphPlan
    from app.execution_plane import PlanValidationError, normalize_analysis_plan

    plan = AnalysisGraphPlan.model_validate(
        {
            "graph_id": "bad_order",
            "hypothesis_id": "h_bad",
            "operators": [
                {"op": "limit", "id": "limited", "input": "orders", "limit": 10},
                {"op": "source", "id": "orders", "asset_id": "orders"},
            ],
            "output": "limited",
            "why": "Invalid order.",
        }
    )

    with pytest.raises(PlanValidationError):
        normalize_analysis_plan(plan, _catalog())


def test_sqlglot_guard_rejects_non_catalog_tables() -> None:
    from app.execution_plane import PlanCompileError, render_readonly_select

    with pytest.raises(PlanCompileError):
        render_readonly_select(
            'SELECT * FROM "other_org_table"',
            allowed_tables={"orders_exec_test"},
            stage="test",
        )

    with pytest.raises(PlanCompileError):
        render_readonly_select(
            'SELECT * FROM "orders_exec_test"; SELECT * FROM "orders_exec_test"',
            allowed_tables={"orders_exec_test"},
            stage="test",
        )


def test_text_filter_literals_are_coerced_to_text() -> None:
    from app.execution_plane.sql import predicate_sql

    assert predicate_sql(
        alias="orders_count",
        observed_type="text",
        operator="<",
        value=2,
    ) == 'src."orders_count" < \'2\''


@pytest.mark.asyncio
async def test_execute_analysis_plan_returns_result_ref() -> None:
    from app.analysis_contracts import AnalysisGraphPlan
    from app.data_plane.naming import quote_ident
    from app.data_plane.storage import db_path, open_duckdb
    from app.execution_plane import execute_analysis_plan

    org_id = uuid4()
    db = open_duckdb(org_id, read_only=False)
    try:
        db.execute(f"CREATE TABLE {quote_ident('orders_exec_test')} (customer_id VARCHAR, total VARCHAR)")
        db.executemany(
            f"INSERT INTO {quote_ident('orders_exec_test')} VALUES (?, ?)",
            [("c1", "120"), ("c1", "230"), ("c2", "90")],
        )
        db.close()

        plan = AnalysisGraphPlan.model_validate(
            {
                "graph_id": "spend_by_customer",
                "hypothesis_id": "h3",
                "operators": [
                    {"op": "source", "id": "orders", "asset_id": "orders"},
                    {
                        "op": "aggregate",
                        "id": "by_customer",
                        "input": "orders",
                        "group_by_field_ids": ["orders.customer_id"],
                        "measures": [
                            {
                                "field_id": "orders.total",
                                "aggregate": "sum",
                                "alias": "total_spent",
                            }
                        ],
                    },
                    {"op": "limit", "id": "limited", "input": "by_customer", "limit": 10},
                ],
                "output": "limited",
                "why": "Spend by customer.",
            }
        )

        result = await execute_analysis_plan(org_id, plan, catalog=_catalog(), max_preview_rows=10)

        assert result.graph_id == "spend_by_customer"
        assert result.row_count == 2
        assert {"customer_id": "c1", "total_spent": 350.0} in result.result_preview
        assert any(line["field_id"] == "orders.total" for line in result.lineage)
    finally:
        with suppress(Exception):
            db.close()
        db_path(org_id).unlink(missing_ok=True)
