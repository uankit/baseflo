from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest


def test_agent_plane_registry_has_prompt_for_every_spec() -> None:
    from app.agent_plane.factory import AgentFactory
    from app.agent_plane.registry import list_agent_specs

    factory = AgentFactory()
    specs = list_agent_specs()

    assert len(specs) == 11
    assert len({spec.name for spec in specs}) == len(specs)
    for spec in specs:
        prompt = factory.prompt_for(spec)
        assert "Single responsibility" in prompt
        agent = factory.create(spec)
        assert agent is factory.create(spec)


def test_agent_plane_dag_has_deterministic_boundaries() -> None:
    from app.agent_plane.graph import agent_plane_dag

    dag = agent_plane_dag()
    by_node = {node["node"]: node for node in dag}

    assert by_node["load_canonical_context"]["kind"] == "runtime"
    assert by_node["relationship_validator"]["kind"] == "runtime"
    assert by_node["plan_validator"]["kind"] == "runtime"
    assert by_node["analysis_runtime"]["kind"] == "runtime_parallel_by_plan"
    assert "relationship_validator" in by_node["pattern_proposer"]["after"]
    assert "analysis_runtime" in by_node["hypothesizer"]["after"]
    assert "hypothesizer" in by_node["action_drafter"]["after"]


def test_agent_plane_system_fields_are_hidden_from_agent_context() -> None:
    from app.agent_plane.context import is_system_field

    assert is_system_field(SimpleNamespace(name="_bf_record_id", profile={}))
    assert is_system_field(SimpleNamespace(name="source__bf_record_id", profile={"system_column": True}))
    assert not is_system_field(SimpleNamespace(name="party_name", profile={"system_column": False}))


def test_agent_runner_hash_is_stable_and_order_insensitive() -> None:
    from app.agent_plane.runner import canonical_json, input_hash

    left = {"b": [2, 1], "a": {"x": "y"}}
    right = {"a": {"x": "y"}, "b": [2, 1]}

    assert canonical_json(left) == canonical_json(right)
    assert input_hash(left) == input_hash(right)


def _business_model_payload() -> dict[str, Any]:
    return {
        "paragraph": "This business sells products and tracks orders.",
        "business_kind": "commerce",
        "primary_currency": "INR",
        "entities": [
            {
                "name": "customer",
                "plural": "customers",
                "description": "People who buy from the business.",
                "primary_asset_id": "asset_customers",
            }
        ],
        "primary_kpis": [
            {
                "name": "revenue",
                "description": "Total money collected.",
                "field_refs": ["field_total"],
                "source_asset_ids": ["asset_orders"],
            }
        ],
        "confidence": 0.8,
    }


def test_agent_model_provider_cache_key_uses_requested_model(monkeypatch: Any) -> None:
    from app.agent_plane.registry import get_agent_spec
    from app.agent_plane.runner import AgentModelProvider
    from app.config import Settings

    settings = Settings(
        BASEFLO_DATABASE_URL="postgresql+asyncpg://baseflo:baseflo@localhost/baseflo_test",
        BASEFLO_SECRET_KEY="test-secret",
        BASEFLO_OPENAI_AGENT_MODEL="gpt-4o-mini",
    )
    monkeypatch.setattr("app.agent_plane.runner.get_settings", lambda: settings)

    assert (
        AgentModelProvider().cache_key_for(get_agent_spec("business_understander"))
        == "gpt-4o-mini"
    )


async def _run_business_understander_with_fake_agent(
    monkeypatch: Any,
    *,
    cached: dict[str, Any] | None,
) -> tuple[Any, dict[str, Any], dict[str, int]]:
    from app.agent_plane.contracts import BusinessModel
    from app.agent_plane.registry import get_agent_spec
    from app.agent_plane.runner import AgentRunner
    from app.config import Settings

    settings = Settings(
        BASEFLO_DATABASE_URL="postgresql+asyncpg://baseflo:baseflo@localhost/baseflo_test",
        BASEFLO_SECRET_KEY="test-secret",
        BASEFLO_OPENAI_AGENT_MODEL="test-model",
    )
    monkeypatch.setattr("app.agent_plane.runner.get_settings", lambda: settings)

    stored: dict[str, Any] = {}
    calls = {"agent": 0}

    async def fake_load_agent_cache(**_kwargs: Any) -> dict[str, Any] | None:
        return cached

    async def fake_store_agent_cache(**kwargs: Any) -> None:
        stored.update(kwargs)

    class FakeAgent:
        async def run(self, _user_message: str, *, model: object) -> SimpleNamespace:
            calls["agent"] += 1
            return SimpleNamespace(output=BusinessModel.model_validate(_business_model_payload()))

    class FakeFactory:
        def create(self, _spec: object) -> FakeAgent:
            return FakeAgent()

    class FakeModelProvider:
        def cache_key_for(self, _spec: object) -> str:
            return "test-model"

        def model_for(self, _spec: object) -> object:
            return object()

    monkeypatch.setattr("app.agent_plane.runner.load_agent_cache", fake_load_agent_cache)
    monkeypatch.setattr("app.agent_plane.runner.store_agent_cache", fake_store_agent_cache)

    runner = AgentRunner(factory=FakeFactory(), model_provider=FakeModelProvider())
    output = await runner.run(
        get_agent_spec("business_understander"),
        {"organization_id": "org_123", "asset_count": 1},
    )
    return output, stored, calls


@pytest.mark.asyncio
async def test_agent_runner_returns_cached_output_without_model_call(
    monkeypatch: Any,
) -> None:
    output, stored, calls = await _run_business_understander_with_fake_agent(
        monkeypatch,
        cached=_business_model_payload(),
    )

    assert output.business_kind == "commerce"
    assert calls["agent"] == 0
    assert stored == {}


@pytest.mark.asyncio
async def test_agent_runner_stores_cache_on_model_success(monkeypatch: Any) -> None:
    output, stored, calls = await _run_business_understander_with_fake_agent(
        monkeypatch,
        cached=None,
    )

    assert output.business_kind == "commerce"
    assert calls["agent"] == 1
    assert stored["scope_key"] == "org:org_123"
    assert stored["agent_name"] == "business_understander"
    assert stored["model_name"] == "test-model"
    assert stored["output"]["business_kind"] == "commerce"
