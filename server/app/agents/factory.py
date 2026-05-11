"""AgentFactory — cached `pydantic_ai.Agent` construction.

Per docs/40-features/ENG-RUNTIME.md §3.4, building Pydantic AI agents is
expensive enough to amortize. We cache by `(agent_name, model_name,
instructions_hash, output_schema_hash)` so a tier escalation rebuilds
with the new model but reuses everything else.
"""

from __future__ import annotations

import hashlib
from collections.abc import Callable
from functools import lru_cache
from typing import TYPE_CHECKING, Any, cast

from pydantic import BaseModel

from app.agents.registry import AgentRegistry
from app.agents.types import AgentSpec
from app.core.config import AgentProvider, get_config
from app.core.errors import BasefloError
from app.observability.logging import get_logger


_validator_logger = get_logger("agents.validator")

if TYPE_CHECKING:
    from pydantic_ai import Agent as PydanticAIAgent


def _hash_str(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:16]


def _instructions_hash(spec_name: str) -> str:
    spec = AgentRegistry.get(spec_name)
    return _hash_str(spec.instructions)


def _output_schema_hash(spec_name: str) -> str:
    spec = AgentRegistry.get(spec_name)
    schema_json = spec.output_type.model_json_schema()
    return _hash_str(repr(sorted(schema_json.items())))


def _provider_config_hash() -> str:
    config = get_config()
    key = ""
    if config.agent_provider is AgentProvider.OPENAI and config.openai_api_key is not None:
        key = config.openai_api_key.get_secret_value()
    return _hash_str(f"{config.agent_provider.value}:{key}")


def _model_for_provider(model_name: str) -> Any:
    config = get_config()
    if config.agent_provider is AgentProvider.OPENAI:
        api_key = (
            config.openai_api_key.get_secret_value().strip()
            if config.openai_api_key is not None
            else ""
        )
        if not api_key:
            raise BasefloError(
                error_code="BF-AGENT-006",
                message=(
                    "OPENAI_API_KEY is required when BASEFLO_AGENT_PROVIDER=openai. "
                    "Set it in the server environment or .env file and restart workers."
                ),
                details={"provider": config.agent_provider.value},
            )

        from pydantic_ai.models.openai import OpenAIChatModel  # noqa: PLC0415
        from pydantic_ai.providers.openai import OpenAIProvider  # noqa: PLC0415

        return OpenAIChatModel(
            cast(Any, model_name),
            provider=OpenAIProvider(api_key=api_key),
        )

    raise BasefloError(
        error_code="BF-AGENT-006",
        message=(
            f"Agent provider {config.agent_provider.value!r} is not wired in this "
            "runtime build."
        ),
        details={"provider": config.agent_provider.value},
    )


def _attach_output_validators(
    agent: PydanticAIAgent[BaseModel, BaseModel],
    spec: AgentSpec[BaseModel, BaseModel],
) -> None:
    if not spec.output_validators:
        return

    from pydantic_ai import ModelRetry, RunContext  # noqa: PLC0415

    for validator in spec.output_validators:

        @agent.output_validator
        def _registered_output_validator(
            ctx: RunContext[BaseModel],
            output: BaseModel,
            *,
            _validator: Callable[..., BaseModel] = validator,
        ) -> BaseModel:
            input_payload = (
                ctx.deps
                if isinstance(ctx.deps, spec.input_type)
                else None
            )
            try:
                return _validator(output, input_payload=input_payload)
            except ModelRetry:
                raise
            except ValueError as exc:
                # Surface the specific check that failed so retries are
                # diagnosable from logs without re-running with a debugger.
                _validator_logger.warning(
                    "agent_output_validator_rejected",
                    agent_name=spec.name,
                    validator=getattr(_validator, "__name__", "anon"),
                    reason=str(exc),
                )
                raise ModelRetry(str(exc)) from exc


@lru_cache(maxsize=256)
def _build_agent_cached(
    agent_name: str,
    model_name: str,
    instructions_hash: str,  # included in cache key  # noqa: ARG001
    output_schema_hash: str,  # included in cache key  # noqa: ARG001
    provider_config_hash: str,  # included in cache key  # noqa: ARG001
) -> PydanticAIAgent[BaseModel, BaseModel]:
    # Local import: pydantic_ai is pulled in lazily so the test harness
    # can swap in fixtures before import.
    from pydantic_ai import Agent as PydanticAIAgent  # noqa: PLC0415
    from pydantic_ai.output import NativeOutput  # noqa: PLC0415
    from pydantic_ai.settings import ModelSettings  # noqa: PLC0415

    spec = cast(AgentSpec[BaseModel, BaseModel], AgentRegistry.get(agent_name))
    # `NativeOutput(..., strict=True)` makes pydantic-ai use the provider's
    # native structured-output API (OpenAI: `response_format={"type":
    # "json_schema", "strict": true, ...}`). The API enforces the schema at
    # generation time — the model literally cannot emit a field that isn't in
    # `output_type`. This eliminates the entire class of "model hallucinated a
    # field name" bugs (which were forcing us into prompt-engineered repair
    # loops) and moves contract enforcement to where it belongs: the API
    # boundary, not prose hints.
    agent = cast(
        PydanticAIAgent[BaseModel, BaseModel],
        PydanticAIAgent(
            model=_model_for_provider(model_name),
            output_type=cast(Any, NativeOutput(spec.output_type, strict=True)),
            instructions=spec.instructions,
            deps_type=spec.input_type,
            model_settings=ModelSettings(temperature=0.0, seed=0),
            retries=spec.max_repair_attempts,
            output_retries=spec.max_repair_attempts,
        ),
    )
    _attach_output_validators(agent, spec)
    return agent


def get_agent(agent_name: str, model_name: str) -> PydanticAIAgent[BaseModel, BaseModel]:
    """Return a cached `pydantic_ai.Agent` for the given configuration.

    Identical (agent, model, instructions, schema) tuples reuse the same instance.
    Changing instructions invalidates the cache automatically via the hash key.
    """
    return _build_agent_cached(
        agent_name=agent_name,
        model_name=model_name,
        instructions_hash=_instructions_hash(agent_name),
        output_schema_hash=_output_schema_hash(agent_name),
        provider_config_hash=_provider_config_hash(),
    )


def clear_factory_cache() -> None:
    """Test-only: drop all cached pydantic_ai.Agent instances."""
    _build_agent_cached.cache_clear()
