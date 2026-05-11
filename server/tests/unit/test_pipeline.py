"""Unit tests for the artifact-centric BuildPipeline."""

from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from app.agents.types import AgentRunResult, AgentRunStatus, ModelTier, TokenUsage
from app.connectors.base import (
    ConnectorToken,
    Row,
    SourceSchema,
)
from app.connectors.base import (
    SourceColumn as ConnectorSourceColumn,
)
from app.connectors.base import (
    SourceTable as ConnectorSourceTable,
)
from app.core.context import TenantCtx, clear_tenant_ctx, set_tenant_ctx
from app.pipeline.build import BuildPipeline, BuildRequest


class _ScalarResult:
    def __init__(self, value: object) -> None:
        self._value = value

    def scalar_one_or_none(self) -> object:
        return self._value


class _FakeConnector:
    async def authenticate(self, credentials: object) -> object:
        raise AssertionError("stored ConnectorToken should not be re-authenticated")

    async def introspect_schema(self, token: ConnectorToken) -> SourceSchema:
        assert token.connector_name == "google_sheets"
        return SourceSchema(
            tables=[
                ConnectorSourceTable(
                    name="orders",
                    columns=[
                        ConnectorSourceColumn(
                            name="order_id",
                            source_type="text",
                            nullable=False,
                            sample_values=["A-100"],
                        )
                    ],
                    primary_key=["order_id"],
                )
            ],
            introspected_at=datetime.now(UTC),
        )

    async def sample_rows(
        self, token: ConnectorToken, table: str, n: int
    ) -> list[Row]:
        assert token.connector_name == "google_sheets"
        assert table == "orders"
        assert n == 5
        return [Row(values={"order_id": "A-100"}, source_id="A-100")]


class TestBuildPipeline:
    @pytest.fixture
    def pipeline(self) -> BuildPipeline:
        session = AsyncMock()
        return BuildPipeline(session)

    @pytest.fixture
    def mock_runtime_result(self) -> AgentRunResult[Any]:
        return AgentRunResult(
            agent_name="SourceAgent",
            output=MagicMock(),
            attempt_count=1,
            repair_attempted=False,
            escalated=False,
            final_status=AgentRunStatus.PASSED,
            model_tier_used=ModelTier.BALANCED,
            model_name_used="gpt-4",
            duration_ms=250,
            usage=TokenUsage(input_tokens=100, output_tokens=50, requests=1),
            started_at=datetime.now(UTC),
            completed_at=datetime.now(UTC),
            agent_run_id=uuid4(),
        )

    @pytest.mark.asyncio
    async def test_source_agent_uses_stored_token_without_reauth(self) -> None:
        from app.agents.source_agent.types import SourceAgentInput, SourceAgentOutput
        from app.artifacts.types import SourceColumn, SourceMap, SourceTable

        organization_id = uuid4()
        project_id = uuid4()
        connector_id = uuid4()
        artifact_id = uuid4()
        connector_model = SimpleNamespace(
            id=connector_id,
            kind="google_sheets",
            config={},
        )
        session = AsyncMock()
        session.execute.return_value = _ScalarResult(connector_model)
        pipeline = BuildPipeline(session)
        token = ConnectorToken(
            connector_name="google_sheets",
            token_id=uuid4(),
            metadata={
                "spreadsheet_id": "sheet_123",
                "access_token": "access",
                "refresh_token": "refresh",
            },
        )
        pipeline._load_connector = AsyncMock(return_value=(_FakeConnector(), token))

        source_map = SourceMap(
            connector_id=connector_id,
            connector_kind="google_sheets",
            tables=[
                SourceTable(
                    name="orders",
                    source_name="Google Sheets",
                    columns=[
                        SourceColumn(
                            name="order_id",
                            semantic_type="IDENTITY",
                            physical_type="TEXT",
                            nullable=False,
                            sample_values=["A-100"],
                        )
                    ],
                    primary_key=["order_id"],
                )
            ],
        )
        pipeline._runtime.run = AsyncMock(
            return_value=AgentRunResult(
                agent_name="SourceAgent",
                output=SourceAgentOutput(source_map=source_map),
                attempt_count=1,
                repair_attempted=False,
                escalated=False,
                final_status=AgentRunStatus.PASSED,
                model_tier_used=ModelTier.BALANCED,
                model_name_used="gpt-4",
                duration_ms=250,
                usage=TokenUsage(input_tokens=100, output_tokens=50, requests=1),
                started_at=datetime.now(UTC),
                completed_at=datetime.now(UTC),
                agent_run_id=uuid4(),
            )
        )
        artifact = MagicMock()
        artifact.header.artifact_id = artifact_id
        artifact.payload = source_map
        pipeline._store.save = AsyncMock(return_value=artifact)
        pipeline._emit_artifact_ready = AsyncMock()

        set_tenant_ctx(
            TenantCtx(
                organization_id=organization_id,
                user_id=None,
                request_id="test",
            )
        )
        try:
            result = await pipeline._run_source_agent(
                project_id,
                connector_id,
                "online store",
            )
        finally:
            clear_tenant_ctx()

        assert result.header.artifact_id == artifact_id
        runtime_input = pipeline._runtime.run.call_args.kwargs["input_payload"]
        assert isinstance(runtime_input, SourceAgentInput)
        assert runtime_input.raw_schema["tables"][0]["name"] == "orders"
        assert runtime_input.sample_rows == [{"order_id": "A-100"}]
        pipeline._store.save.assert_awaited_once()
        assert pipeline._store.save.call_args.kwargs["payload"] == source_map

    @pytest.mark.asyncio
    async def test_build_request_structure(self) -> None:
        req = BuildRequest(
            project_id=uuid4(),
            connector_ids=[uuid4()],
            business_description="A yoga studio with bookings and payments.",
        )
        assert len(req.connector_ids) == 1
        assert "yoga" in req.business_description.lower()

    @pytest.mark.asyncio
    async def test_source_agent_validator_rejects_empty_tables(self) -> None:
        from app.agents.source_agent.agent import _validate_output
        from app.agents.source_agent.types import SourceAgentOutput
        from app.artifacts.types import SourceMap

        sm = SourceMap(connector_id=uuid4(), connector_kind="csv", tables=[])
        out = SourceAgentOutput(source_map=sm)
        with pytest.raises(ValueError, match="at least one table"):
            _validate_output(out, input_payload=None)

    @pytest.mark.asyncio
    async def test_reconciliation_agent_validator_rejects_empty(self) -> None:
        from app.agents.reconciliation_agent.agent import _validate_output
        from app.agents.reconciliation_agent.types import (
            ReconciliationAgentOutput,
        )
        from app.artifacts.types import EntityGraph

        out = ReconciliationAgentOutput(entity_graph=EntityGraph(entities=[], unresolved=[]))
        with pytest.raises(ValueError, match="at least one entity"):
            _validate_output(out, input_payload=None)

    @pytest.mark.asyncio
    async def test_schema_agent_validator_rejects_missing_id(self) -> None:
        from datetime import UTC, datetime

        from app.agents.schema_agent.agent import _validate_output
        from app.agents.schema_agent.types import SchemaAgentOutput
        from app.engines.schema.ir import ColumnIR, SchemaIR, TableIR
        ir = SchemaIR(
            composed_at=datetime.now(UTC),
            composed_by="test",
            tables=[
                TableIR(
                    name="bad",
                    label="Bad Table",
                    purpose="Test table missing id",
                    grain="one row per test",
                    primary_key=["id"],
                    columns=[
                        ColumnIR(
                            name="name",
                            label="Name",
                            semantic_type="free_text",
                            physical_type="text",
                            nullable=True,
                        )
                    ],
                )
            ],
        )
        out = SchemaAgentOutput(schema_ir=ir, assumptions=[])
        with pytest.raises(ValueError, match="primary_key references missing columns"):
            _validate_output(out, input_payload=None)

    @pytest.mark.asyncio
    async def test_schema_agent_normalizes_missing_money_currency_column(self) -> None:
        from app.agents.schema_agent.agent import _validate_output
        from app.agents.schema_agent.types import SchemaAgentOutput
        from app.engines.schema.compatibility import validate as validate_ir
        from app.engines.schema.ir import ColumnIR, SchemaIR, TableIR

        ir = SchemaIR(
            composed_at=datetime.now(UTC),
            composed_by="SchemaAgent",
            tables=[
                TableIR(
                    name="product",
                    label="Product",
                    purpose="Products for sale",
                    grain="one row per product",
                    primary_key=["id"],
                    columns=[
                        ColumnIR(
                            name="id",
                            label="ID",
                            semantic_type="identity",
                            physical_type="uuid",
                            nullable=False,
                        ),
                        ColumnIR(
                            name="price",
                            label="Price",
                            semantic_type="money",
                            physical_type="numeric",
                            nullable=True,
                            currency_column="currency_code",
                        ),
                    ],
                )
            ],
        )

        out = _validate_output(SchemaAgentOutput(schema_ir=ir, assumptions=[]))
        money = out.schema_ir.tables[0].columns[1]

        assert money.physical_type == "bigint"
        assert money.is_minor_unit is True
        assert money.currency_column is None
        assert validate_ir(out.schema_ir).passed

    @pytest.mark.asyncio
    async def test_schema_agent_normalizes_non_text_money_currency_column(self) -> None:
        from app.agents.schema_agent.agent import _validate_output
        from app.agents.schema_agent.types import SchemaAgentOutput
        from app.engines.schema.compatibility import validate as validate_ir
        from app.engines.schema.ir import ColumnIR, SchemaIR, TableIR

        ir = SchemaIR(
            composed_at=datetime.now(UTC),
            composed_by="SchemaAgent",
            tables=[
                TableIR(
                    name="order",
                    label="Order",
                    purpose="Customer orders",
                    grain="one row per order",
                    primary_key=["id"],
                    columns=[
                        ColumnIR(
                            name="id",
                            label="ID",
                            semantic_type="identity",
                            physical_type="uuid",
                            nullable=False,
                        ),
                        ColumnIR(
                            name="total_amount",
                            label="Total Amount",
                            semantic_type="money",
                            physical_type="numeric",
                            nullable=True,
                            currency_column="currency_code",
                        ),
                        ColumnIR(
                            name="currency_code",
                            label="Currency Code",
                            semantic_type="count",
                            physical_type="int",
                            nullable=True,
                        ),
                    ],
                )
            ],
        )

        out = _validate_output(SchemaAgentOutput(schema_ir=ir, assumptions=[]))
        columns = {col.name: col for col in out.schema_ir.tables[0].columns}

        assert columns["total_amount"].physical_type == "bigint"
        assert columns["total_amount"].is_minor_unit is True
        assert columns["total_amount"].currency_column == "currency_code"
        assert columns["currency_code"].semantic_type == "category"
        assert columns["currency_code"].physical_type == "text"
        assert validate_ir(out.schema_ir).passed
