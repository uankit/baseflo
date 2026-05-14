from __future__ import annotations

from uuid import uuid4

import pytest
from pydantic import ValidationError as PydanticValidationError

from app.agentic import (
    AggregateMeasure,
    AggregateNode,
    AnalysisGraph,
    AnalysisRuntime,
    AssetRole,
    FilterNode,
    FilterPredicate,
    JoinNode,
    LimitNode,
    RankNode,
    SourceNode,
)
from app.agents import (
    BusinessEntity,
    BusinessKpi,
    BusinessModel,
    EntityGraph,
    FormulaCompileError,
    FormulaFieldRef,
    FormulaMeasure,
    FormulaSpec,
    GraphEdge,
    GraphNode,
    compile_formula,
)
from app.core.errors import ValidationError as AppValidationError
from app.core.context import TenantCtx
from app.db.models import OperatingAsset, OperatingColumn


def test_analysis_graph_rejects_raw_sql_shape() -> None:
    with pytest.raises(PydanticValidationError):
        AnalysisGraph.model_validate(
            {
                "graph_id": "bad",
                "hypothesis_type": "raw_sql_attempt",
                "nodes": [{"op": "source", "id": "source", "table": "orders", "sql": "select * from orders"}],
                "output_node": "source",
                "lineage": [],
                "why": "Trying to smuggle SQL through a typed node.",
            }
        )


def test_analysis_graph_compiles_generic_operator_dsl() -> None:
    org_id = uuid4()
    asset = OperatingAsset(
        id=uuid4(),
        organization_id=org_id,
        qualified_name="source__orders",
        source_name="source",
        table_label="orders",
        row_count=10,
        column_count=2,
        status="active",
        profile={},
    )
    columns = [
        OperatingColumn(
            id=uuid4(),
            organization_id=org_id,
            asset_id=asset.id,
            name="customer_id",
            observed_type="text",
            semantic_type="identity_candidate",
            null_rate=0,
            unique_count=10,
            confidence=0.8,
            sample_values=[],
            profile={},
        ),
        OperatingColumn(
            id=uuid4(),
            organization_id=org_id,
            asset_id=asset.id,
            name="total",
            observed_type="number",
            semantic_type="measure_candidate",
            null_rate=0,
            unique_count=10,
            confidence=0.8,
            sample_values=[],
            profile={},
        ),
    ]
    graph = AnalysisGraph(
        graph_id="customer_total",
        hypothesis_type="value_event_value_review",
        nodes=[
            SourceNode(id="source", table="source__orders"),
            AggregateNode(
                id="aggregate",
                input="source",
                group_by=["customer_id"],
                measures=[AggregateMeasure(function="sum", column="total", alias="sum_total")],
            ),
            RankNode(id="rank", input="aggregate", order_by="sum_total", direction="desc"),
            LimitNode(id="output", input="rank", limit=5),
        ],
        output_node="output",
        lineage=[{"table": "source__orders", "column": "total"}],
        why="Rank customers by total.",
    )

    sql = AnalysisRuntime(assets=[asset], columns_by_asset={asset.id: columns}).compile(graph)

    # sqlglot normalises SQL — function names come back uppercase.
    lowered = sql.lower()
    assert "rank() over" in lowered
    assert '"source__orders"' in sql
    assert "try_cast" in lowered


@pytest.mark.asyncio
async def test_analysis_runtime_executes_without_agent_sql(monkeypatch: pytest.MonkeyPatch) -> None:
    org_id = uuid4()
    asset = OperatingAsset(
        id=uuid4(),
        organization_id=org_id,
        qualified_name="source__orders",
        source_name="source",
        table_label="orders",
        row_count=10,
        column_count=2,
        status="active",
        profile={},
    )
    graph = AnalysisGraph(
        graph_id="rows",
        hypothesis_type="row_review",
        nodes=[SourceNode(id="source", table="source__orders"), LimitNode(id="output", input="source", limit=2)],
        output_node="output",
        lineage=[{"table": "source__orders"}],
        why="Preview rows.",
    )

    def fake_safe_query(_org_id, sql: str, *, max_rows: int) -> list[dict[str, object]]:
        assert "SELECT" in sql.upper()
        assert max_rows >= 1
        return [{"id": "1"}, {"id": "2"}]

    monkeypatch.setattr("app.agentic.safe_query", fake_safe_query)
    result = await AnalysisRuntime(assets=[asset], columns_by_asset={}).execute(
        TenantCtx(user_id=uuid4(), organization_id=org_id),
        graph,
    )

    assert result.row_count == 2
    assert result.result_preview == [{"id": "1"}, {"id": "2"}]


def test_agent_factory_is_unconfigured_without_key(monkeypatch: pytest.MonkeyPatch) -> None:
    """Without an OpenAI key (and without a test override), agent_is_configured is False."""
    from app.agents._model import agent_is_configured, use_test_model

    use_test_model(None)
    monkeypatch.setattr(
        "app.agents._model.get_settings",
        lambda: type("S", (), {"openai_api_key": None, "openai_model": "gpt-4o-mini"})(),
    )
    assert agent_is_configured() is False


def test_agent_factory_uses_test_override() -> None:
    """A test override makes the factory report configured and return that model."""
    from pydantic_ai.models.test import TestModel

    from app.agents._model import agent_is_configured, get_default_model, use_test_model

    override = TestModel()
    use_test_model(override)
    try:
        assert agent_is_configured() is True
        assert get_default_model() is override
    finally:
        use_test_model(None)


def test_agent_factory_caches_configured_openai_model(monkeypatch: pytest.MonkeyPatch) -> None:
    from pydantic import SecretStr

    import app.agents._model as _model

    class FakeOpenAIModel:
        def __init__(self, model_name: str) -> None:
            self.model_name = model_name

    calls: list[str] = []

    def fake_model(model_name: str) -> FakeOpenAIModel:
        calls.append(model_name)
        return FakeOpenAIModel(model_name)

    monkeypatch.setattr(
        _model,
        "get_settings",
        lambda: type(
            "S",
            (),
            {
                "openai_api_key": SecretStr("test-key"),
                "openai_model": "gpt-4o-mini",
                "openai_agent_model": "gpt-4o",
            },
        )(),
    )
    monkeypatch.setattr(_model, "OpenAIChatModel", fake_model)
    monkeypatch.setattr(_model, "_MODEL_CACHE", None)
    _model.use_test_model(None)

    first = _model.get_default_model()
    second = _model.get_default_model()

    assert first is second
    assert calls == ["gpt-4o"]


def test_agent_retry_delay_uses_openai_rate_limit_hint(monkeypatch: pytest.MonkeyPatch) -> None:
    from pydantic import SecretStr
    from pydantic_ai.exceptions import ModelHTTPError

    import app.agents._model as _model

    monkeypatch.setattr(
        _model,
        "get_settings",
        lambda: type(
            "S",
            (),
            {
                "openai_api_key": SecretStr("test-key"),
                "openai_model": "gpt-4o-mini",
                "openai_agent_model": "gpt-4o",
                "openai_agent_retry_max_seconds": 20.0,
                "openai_agent_retry_base_seconds": 1.0,
            },
        )(),
    )
    exc = ModelHTTPError(
        status_code=429,
        model_name="gpt-4o",
        body={"message": "Rate limit reached. Please try again in 3.668s."},
    )

    assert _model._retry_delay_seconds(exc, attempt=0) == pytest.approx(4.168)


def _asset(
    org_id,
    name: str,
    columns: list[tuple[str, str]],
) -> tuple[OperatingAsset, list[OperatingColumn]]:
    asset = OperatingAsset(
        id=uuid4(),
        organization_id=org_id,
        qualified_name=name,
        source_name=name.split("__", 1)[0],
        table_label=name,
        row_count=10,
        column_count=len(columns),
        status="active",
        profile={},
    )
    return asset, [
        OperatingColumn(
            id=uuid4(),
            organization_id=org_id,
            asset_id=asset.id,
            name=column_name,
            observed_type=observed_type,
            semantic_type="measure_candidate" if observed_type == "number" else "identity_candidate",
            null_rate=0,
            unique_count=10,
            confidence=0.8,
            sample_values=[],
            profile={},
        )
        for column_name, observed_type in columns
    ]


def test_asset_role_sanitizer_keeps_only_real_columns() -> None:
    from app.agentic import _sanitize_asset_role

    org_id = uuid4()
    asset, columns = _asset(
        org_id,
        "shopify__products",
        [("id", "text"), ("title", "text"), ("total_inventory", "number")],
    )
    role = AssetRole(
        asset_id="wrong",
        qualified_name="wrong_table",
        role="entity",
        entity_type="supplier",
        keys=["id", "product_id"],
        time_dim="created_at",
        measures=["total_inventory", "made_up_total"],
        tags=["catalog"],
        why="Products in Shopify.",
        confidence=0.95,
    )

    sanitized = _sanitize_asset_role(
        role,
        asset=asset,
        columns=columns,
        business_model={"entities": [{"name": "product"}]},
    )

    assert sanitized.asset_id == str(asset.id)
    assert sanitized.qualified_name == "shopify__products"
    assert sanitized.entity_type == "unknown"
    assert sanitized.keys == ["id"]
    assert sanitized.time_dim is None
    assert sanitized.measures == ["total_inventory"]
    assert sanitized.confidence == 0.6


def test_business_model_sanitizer_keeps_only_real_assets_and_columns() -> None:
    from app.agentic import _sanitize_business_model

    org_id = uuid4()
    orders, order_cols = _asset(
        org_id,
        "shopify__orders",
        [("id", "text"), ("total_price", "number")],
    )
    products, product_cols = _asset(
        org_id,
        "shopify__products",
        [("id", "text"), ("title", "text")],
    )
    model = BusinessModel(
        paragraph="A Shopify store with orders and products.",
        business_kind="shopify store",
        entities=[
            BusinessEntity(
                name="order",
                plural="orders",
                description="Orders placed in Shopify.",
                primary_asset="shopify__orderz",
                related_assets=["shopify__orders", "made_up__table"],
            ),
            BusinessEntity(
                name="supplier",
                plural="suppliers",
                description="Missing supplier records.",
                primary_asset="made_up__suppliers",
                related_assets=[],
            ),
        ],
        primary_kpis=[
            BusinessKpi(
                name="revenue",
                description="Order value.",
                measure_column="shopify__orders.total_price",
                derived_from=["shopify__orders", "fake__orders"],
            ),
            BusinessKpi(
                name="supplier score",
                description="Supplier health.",
                measure_column="shopify__orders.total_orders",
                derived_from=["fake__suppliers"],
            ),
        ],
        confidence=0.9,
    )

    sanitized = _sanitize_business_model(
        model,
        assets=[orders, products],
        columns_by_asset={orders.id: order_cols, products.id: product_cols},
    )

    assert [entity.name for entity in sanitized.entities] == ["order"]
    assert sanitized.entities[0].primary_asset == "shopify__orders"
    assert sanitized.entities[0].related_assets == ["shopify__orders"]
    assert sanitized.primary_kpis[0].measure_column == "shopify__orders.total_price"
    assert sanitized.primary_kpis[0].derived_from == ["shopify__orders"]
    assert sanitized.primary_kpis[1].measure_column is None
    assert sanitized.primary_kpis[1].derived_from == []
    assert sanitized.confidence == 0.65


def test_analysis_runtime_rejects_unknown_columns_before_duckdb() -> None:
    org_id = uuid4()
    asset, columns = _asset(org_id, "source__orders", [("orders_count", "number"), ("total_spent", "number")])
    graph = AnalysisGraph(
        graph_id="bad_column",
        hypothesis_type="bad_column",
        nodes=[
            SourceNode(id="source", table="source__orders"),
            AggregateNode(
                id="aggregate",
                input="source",
                group_by=["total_orders"],
                measures=[AggregateMeasure(function="sum", column="total_spent", alias="value")],
            ),
        ],
        output_node="aggregate",
        lineage=[],
        why="Should fail before DuckDB sees a guessed column.",
    )

    with pytest.raises(AppValidationError, match="total_orders"):
        AnalysisRuntime(assets=[asset], columns_by_asset={asset.id: columns}).compile(graph)


def test_analysis_runtime_namespaces_join_outputs_without_star_collision() -> None:
    org_id = uuid4()
    orders, order_cols = _asset(
        org_id,
        "shopify__orders",
        [("id", "text"), ("customer_id", "text"), ("total_price", "number")],
    )
    transactions, transaction_cols = _asset(
        org_id,
        "shopify__transactions",
        [("id", "text"), ("order_id", "text"), ("amount", "number")],
    )
    graph = AnalysisGraph(
        graph_id="join_aliases",
        hypothesis_type="join_aliases",
        nodes=[
            SourceNode(id="orders", table="shopify__orders", namespace="order"),
            SourceNode(id="transactions", table="shopify__transactions", namespace="transaction"),
            JoinNode(
                id="joined",
                left_input="orders",
                right_input="transactions",
                left_key="order__id",
                right_key="transaction__order_id",
            ),
            AggregateNode(
                id="aggregate",
                input="joined",
                group_by=["order__customer_id"],
                measures=[AggregateMeasure(function="sum", column="transaction__amount", alias="paid")],
            ),
        ],
        output_node="aggregate",
        lineage=[],
        why="Join orders to payments.",
    )

    sql = AnalysisRuntime(
        assets=[orders, transactions],
        columns_by_asset={orders.id: order_cols, transactions.id: transaction_cols},
    ).compile(graph)

    assert "lhs.*" not in sql
    assert "rhs.*" not in sql
    assert '"order__customer_id"' in sql
    assert '"transaction__amount"' in sql


def test_analysis_runtime_casts_numeric_filter_values() -> None:
    org_id = uuid4()
    products, product_cols = _asset(
        org_id,
        "shopify__products",
        [("title", "text"), ("total_inventory", "text")],
    )
    graph = AnalysisGraph(
        graph_id="numeric_filter",
        hypothesis_type="numeric_filter",
        nodes=[
            SourceNode(id="products", table="shopify__products", namespace="product"),
            FilterNode(
                id="low_stock",
                input="products",
                predicates=[
                    FilterPredicate(column="product__total_inventory", operator="<", value=5),
                ],
            ),
            AggregateNode(
                id="aggregate",
                input="low_stock",
                group_by=["product__title"],
                measures=[AggregateMeasure(function="count", column=None, alias="products")],
            ),
        ],
        output_node="aggregate",
        lineage=[],
        why="Find products below a stock threshold.",
    )

    sql = AnalysisRuntime(assets=[products], columns_by_asset={products.id: product_cols}).compile(graph)

    assert 'TRY_CAST("product__total_inventory" AS DOUBLE) < 5' in sql


def test_formula_compiler_plans_multi_hop_business_join() -> None:
    org_id = uuid4()
    customers, customer_cols = _asset(org_id, "shopify__customers", [("id", "text"), ("email", "text")])
    orders, order_cols = _asset(org_id, "shopify__orders", [("id", "text"), ("customer_id", "text")])
    transactions, transaction_cols = _asset(
        org_id,
        "shopify__transactions",
        [("order_id", "text"), ("amount", "number")],
    )
    graph = EntityGraph(
        nodes=[
            GraphNode(entity="customer", asset_qualified_name="shopify__customers", label="Customers", why="People who buy."),
            GraphNode(entity="order", asset_qualified_name="shopify__orders", label="Orders", why="Purchases."),
            GraphNode(entity="transaction", asset_qualified_name="shopify__transactions", label="Transactions", why="Payments."),
        ],
        edges=[
            GraphEdge(
                left_entity="customer",
                left_table="shopify__customers",
                left_key="id",
                right_entity="order",
                right_table="shopify__orders",
                right_key="customer_id",
                cardinality="one_to_many",
                meaning="Customers place orders.",
                confidence=0.9,
                validated=True,
            ),
            GraphEdge(
                left_entity="order",
                left_table="shopify__orders",
                left_key="id",
                right_entity="transaction",
                right_table="shopify__transactions",
                right_key="order_id",
                cardinality="one_to_many",
                meaning="Orders have payment transactions.",
                confidence=0.9,
                validated=True,
            ),
        ],
    )
    spec = FormulaSpec(
        team_id="sales",
        formula_id="customer_paid_value",
        why="Sales wants the customers driving collected payment value.",
        title="Customers by paid value",
        target_entity="customer",
        group_by_field=FormulaFieldRef(entity="customer", field="email"),
        measures=[
            FormulaMeasure(
                field=FormulaFieldRef(entity="transaction", field="amount"),
                aggregate="sum",
                alias="paid_value",
            )
        ],
        order_by_alias="paid_value",
        expected_shape="Customers ranked by transaction amount.",
    )

    plan = compile_formula(
        spec,
        graph,
        assets=[customers, orders, transactions],
        columns_by_asset={
            customers.id: customer_cols,
            orders.id: order_cols,
            transactions.id: transaction_cols,
        },
    )

    joins = [node for node in plan.nodes if node.op == "join"]
    aggregate = next(node for node in plan.nodes if node.op == "aggregate")
    assert len(joins) == 2
    assert aggregate.group_by == ["customer__email"]
    assert aggregate.measures[0].column == "transaction__amount"


def test_formula_compiler_allows_relationship_surface_tables() -> None:
    org_id = uuid4()
    products, product_cols = _asset(org_id, "shopify__products", [("id", "text"), ("title", "text")])
    line_items, line_item_cols = _asset(
        org_id,
        "shopify__order_line_items",
        [("product_id", "text"), ("quantity", "number")],
    )
    graph = EntityGraph(
        nodes=[
            GraphNode(entity="product", asset_qualified_name="shopify__products", label="Products", why="Catalog items."),
            GraphNode(entity="order", asset_qualified_name="shopify__orders", label="Orders", why="Purchases."),
        ],
        edges=[
            GraphEdge(
                left_entity="product",
                left_table="shopify__products",
                left_key="id",
                right_entity="order",
                right_table="shopify__order_line_items",
                right_key="product_id",
                cardinality="one_to_many",
                meaning="Products appear on order line items.",
                confidence=0.9,
                validated=True,
            ),
        ],
    )
    spec = FormulaSpec(
        team_id="marketing",
        formula_id="top_products_by_units",
        why="Marketing wants products with current demand.",
        title="Products by units sold",
        target_entity="product",
        group_by_field=FormulaFieldRef(entity="product", field="title"),
        measures=[
            FormulaMeasure(
                field=FormulaFieldRef(
                    entity="order",
                    field="quantity",
                    surface_table="shopify__order_line_items",
                ),
                aggregate="sum",
                alias="units_sold",
            )
        ],
        order_by_alias="units_sold",
        expected_shape="Products ranked by units sold.",
    )

    plan = compile_formula(
        spec,
        graph,
        assets=[products, line_items],
        columns_by_asset={products.id: product_cols, line_items.id: line_item_cols},
    )

    joins = [node for node in plan.nodes if node.op == "join"]
    aggregate = next(node for node in plan.nodes if node.op == "aggregate")
    assert len(joins) == 1
    assert joins[0].right_key == "order__product_id"
    assert aggregate.group_by == ["product__title"]
    assert aggregate.measures[0].column == "order__quantity"


def test_formula_compiler_grounds_missing_money_measure_refs() -> None:
    org_id = uuid4()
    customers, customer_cols = _asset(
        org_id,
        "shopify__customers",
        [("email", "text"), ("total_spent", "number"), ("orders_count", "number")],
    )
    graph = EntityGraph(
        nodes=[
            GraphNode(entity="customer", asset_qualified_name="shopify__customers", label="Customers", why="People who buy."),
        ],
        edges=[],
    )
    spec = FormulaSpec(
        team_id="marketing",
        formula_id="top_customers_by_spend",
        why="Marketing wants to find the customers with the strongest spend signal.",
        title="Top customers by spend",
        target_entity="customer",
        group_by_field=FormulaFieldRef(entity="customer", field="email"),
        measures=[FormulaMeasure(field=None, aggregate="sum", alias="total_spend")],
        order_by_alias="total_spend",
        expected_shape="Customers ranked by total spend.",
    )

    plan = compile_formula(
        spec,
        graph,
        assets=[customers],
        columns_by_asset={customers.id: customer_cols},
    )

    aggregate = next(node for node in plan.nodes if node.op == "aggregate")
    assert aggregate.measures[0].column == "customer__total_spent"


def test_formula_compiler_grounds_missing_average_order_value_ref() -> None:
    org_id = uuid4()
    orders, order_cols = _asset(
        org_id,
        "shopify__orders",
        [("name", "text"), ("total_price", "number"), ("line_items_quantity", "number")],
    )
    graph = EntityGraph(
        nodes=[
            GraphNode(entity="order", asset_qualified_name="shopify__orders", label="Orders", why="Purchases."),
        ],
        edges=[],
    )
    spec = FormulaSpec(
        team_id="marketing",
        formula_id="average_order_value",
        why="Marketing wants to understand average order value.",
        title="Average order value",
        target_entity="order",
        group_by_field=FormulaFieldRef(entity="order", field="name"),
        measures=[FormulaMeasure(field=None, aggregate="avg", alias="average_order_value")],
        order_by_alias="average_order_value",
        expected_shape="Orders ranked by average order value.",
    )

    plan = compile_formula(
        spec,
        graph,
        assets=[orders],
        columns_by_asset={orders.id: order_cols},
    )

    aggregate = next(node for node in plan.nodes if node.op == "aggregate")
    assert aggregate.measures[0].column == "order__total_price"


def test_formula_compiler_rejects_unknown_entity_and_field_with_candidates() -> None:
    org_id = uuid4()
    orders, order_cols = _asset(
        org_id,
        "shopify__orders",
        [("orders_count", "number"), ("total_spent", "number")],
    )
    graph = EntityGraph(
        nodes=[
            GraphNode(entity="order", asset_qualified_name="shopify__orders", label="Orders", why="Purchases."),
        ],
        edges=[],
    )
    unknown_entity = FormulaSpec(
        team_id="ops",
        formula_id="supplier_check",
        why="Ops asked for supplier analysis.",
        title="Supplier check",
        target_entity="supplier",
        group_by_field=FormulaFieldRef(entity="supplier", field="name"),
        measures=[FormulaMeasure(field=None, aggregate="count", alias="count")],
        order_by_alias="count",
        expected_shape="Suppliers ranked by count.",
    )
    with pytest.raises(FormulaCompileError, match="order"):
        compile_formula(unknown_entity, graph, assets=[orders], columns_by_asset={orders.id: order_cols})

    bad_field = FormulaSpec(
        team_id="sales",
        formula_id="order_totals",
        why="Sales wants order volume.",
        title="Order totals",
        target_entity="order",
        group_by_field=FormulaFieldRef(entity="order", field="total_orders"),
        measures=[FormulaMeasure(field=FormulaFieldRef(entity="order", field="total_spent"), aggregate="sum", alias="spent")],
        order_by_alias="spent",
        expected_shape="Orders ranked by spend.",
    )
    with pytest.raises(FormulaCompileError, match="orders_count"):
        compile_formula(bad_field, graph, assets=[orders], columns_by_asset={orders.id: order_cols})
