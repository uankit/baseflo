"""AgentRuntime — the orchestrator that runs a registered agent.

Per docs/40-features/ENG-RUNTIME.md:

- Resolves the model tier and name from `model_routing`.
- Acquires per-tenant concurrency.
- Builds (or retrieves cached) `pydantic_ai.Agent` via `factory.get_agent`.
- Runs with output validators in place; on `ModelRetry` Pydantic AI itself
  retries up to `spec.max_repair_attempts`.
- On exhaustion, escalates to the next tier per `escalation_path`.
- On final exhaustion at `reasoning`, raises `BF-AGENT-005`.
- Captures real provider token usage; never zeros.

Notes:
- The runtime is fully async. There is NO `asyncio.run(...)` in this module
  (the audit caught that regression; we are not repeating it).
- Trace persistence happens AFTER the artifact commits, on a separate session,
  via `app.orchestration.trace` (added in M0.5).
"""

from __future__ import annotations

import time
from datetime import UTC, datetime
from typing import TYPE_CHECKING, TypeVar, cast
from uuid import UUID

from pydantic import BaseModel

from app.agents import factory
from app.agents.concurrency import get_default_semaphore
from app.agents.model_routing import escalation_path, resolve_model_name
from app.agents.types import AgentRunResult, AgentRunStatus, AgentSpec, ModelTier, TokenUsage
from app.core.context import set_agent_name, set_agent_run_id
from app.core.errors import BasefloError
from app.core.ids import new_uuid7
from app.observability.logging import get_logger

if TYPE_CHECKING:
    from pydantic_ai import Agent as PydanticAIAgent


_InT = TypeVar("_InT", bound=BaseModel)
_OutT = TypeVar("_OutT", bound=BaseModel)

logger = get_logger("agents.runtime")


class AgentRuntime:
    """Run a registered agent with repair, escalation, concurrency, and tracing."""

    def __init__(self) -> None:
        self._semaphore = get_default_semaphore()

    async def run(
        self,
        *,
        spec: AgentSpec[_InT, _OutT],
        input_payload: _InT,
        tenant_id: UUID,
    ) -> AgentRunResult[_OutT]:
        """Run a typed agent. The result's `output` is `spec.output_type`.

        The runtime is generic over the spec's input/output types so callers
        get a precisely-typed `AgentRunResult` — no downcasts, no isinstance
        guards needed at the call site. Per docs/05-coding-rules.md §2.1.
        """
        if not isinstance(input_payload, spec.input_type):
            raise BasefloError(
                error_code="BF-AGENT-003",
                message=(
                    f"Agent {spec.name!r} expects {spec.input_type.__name__}; "
                    f"received {type(input_payload).__name__}."
                ),
                status_code=500,
            )

        run_id = new_uuid7()
        set_agent_run_id(run_id)
        set_agent_name(spec.name)

        async with self._semaphore.acquire(tenant_id):
            return await self._run_with_escalation(
                spec=spec,
                input_payload=input_payload,
                run_id=run_id,
                start_tier=spec.model_tier,
            )

    async def _run_with_escalation(
        self,
        *,
        spec: AgentSpec[_InT, _OutT],
        input_payload: _InT,
        run_id: UUID,
        start_tier: ModelTier,
    ) -> AgentRunResult[_OutT]:
        attempt_count = 0
        escalated = False
        started_at = datetime.now(UTC)
        wall_start = time.perf_counter()

        last_error: BasefloError | None = None
        for tier in escalation_path(start_tier):
            model_name = resolve_model_name(tier)
            # Module-attribute lookup (`factory.get_agent`) — never `from … import get_agent`
            # — so test fixtures that monkey-patch `factory.get_agent` are honoured at call time.
            agent = factory.get_agent(spec.name, model_name)
            try:
                output, usage = await self._invoke(agent, input_payload)
            except BasefloError as exc:  # validator exhaustion at this tier
                last_error = exc
                escalated = tier != start_tier or escalated
                attempt_count += spec.max_repair_attempts
                logger.warning(
                    "agent_run_tier_exhausted",
                    agent_name=spec.name,
                    tier=tier.value,
                    model_name=model_name,
                    error_code=exc.error_code,
                    error_message=exc.message,
                    error_details=exc.details,
                )
                continue

            attempt_count += 1
            duration_ms = int((time.perf_counter() - wall_start) * 1000)
            return AgentRunResult(
                agent_name=spec.name,
                output=cast(_OutT, output),
                attempt_count=attempt_count,
                repair_attempted=attempt_count > 1,
                escalated=escalated,
                final_status=AgentRunStatus.PASSED,
                model_tier_used=tier,
                model_name_used=model_name,
                duration_ms=duration_ms,
                usage=usage,
                started_at=started_at,
                completed_at=datetime.now(UTC),
                agent_run_id=run_id,
            )

        # All tiers exhausted.
        raise BasefloError(
            error_code="BF-AGENT-005",
            message=(
                f"Agent {spec.name!r} failed after escalation to reasoning tier. "
                "Surface as terminal failure."
            ),
            status_code=502,
            details={
                "agent_name": spec.name,
                "agent_run_id": str(run_id),
                "last_error_code": last_error.error_code if last_error else None,
                "last_error_message": last_error.message if last_error else None,
            },
            cause=last_error,
        )

    async def _invoke(
        self,
        agent: PydanticAIAgent[BaseModel, BaseModel],
        input_payload: BaseModel,
    ) -> tuple[BaseModel, TokenUsage]:
        """Execute one Pydantic AI run; capture real usage.

        Pydantic AI itself runs validator-driven `ModelRetry` loops up to
        `spec.max_repair_attempts` (set on the Agent). We catch its terminal
        exception type and translate it into `BF-AGENT-003`.
        """
        # Local import keeps the test harness flexible.
        from pydantic_ai.exceptions import (  # noqa: PLC0415
            UnexpectedModelBehavior,
            UsageLimitExceeded,
        )

        try:
            result = await agent.run(
                input_payload.model_dump_json(),
                deps=input_payload,
            )
        except UnexpectedModelBehavior as exc:
            raise BasefloError(
                error_code="BF-AGENT-003",
                message=f"Agent produced invalid structured output: {exc}",
                status_code=502,
                cause=exc,
            ) from exc
        except UsageLimitExceeded as exc:
            raise BasefloError(
                error_code="BF-AGENT-004",
                message="Agent exceeded provider usage limit.",
                status_code=429,
                cause=exc,
            ) from exc

        usage = self._extract_usage(result)
        return result.output, usage

    def _extract_usage(self, result: object) -> TokenUsage:
        """Read real token usage from a Pydantic AI RunResult.

        Falls back to zeros only if the provider/test harness genuinely returned
        nothing. The audit flagged a regression where usage was hardcoded zero;
        we never default to zero when real values are available.
        """
        usage_method = getattr(result, "usage", None)
        if usage_method is None:
            return TokenUsage()
        try:
            data = usage_method() if callable(usage_method) else usage_method
        except Exception:  # noqa: BLE001 — defensive: provider usage parsing
            return TokenUsage()
        return TokenUsage(
            input_tokens=int(getattr(data, "input_tokens", 0) or 0),
            output_tokens=int(getattr(data, "output_tokens", 0) or 0),
            cache_read_tokens=int(getattr(data, "cache_read_tokens", 0) or 0),
            cache_write_tokens=int(getattr(data, "cache_write_tokens", 0) or 0),
            requests=int(getattr(data, "requests", 0) or 0),
        )


_default_runtime: AgentRuntime | None = None


def get_default_runtime() -> AgentRuntime:
    global _default_runtime
    if _default_runtime is None:
        _default_runtime = AgentRuntime()
    return _default_runtime


def reset_default_runtime() -> None:
    """Test-only."""
    global _default_runtime
    _default_runtime = None
