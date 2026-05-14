"""Model factory + run helpers for capability agents.

Single source of truth for which LLM agents call. Picks the configured
provider/model from settings and exposes a TestModel hook so the pipeline
runs in CI without keys.
"""

from __future__ import annotations

import asyncio
import logging
import os
import re
from typing import Any

from pydantic_ai import Agent
from pydantic_ai.exceptions import ModelHTTPError
from pydantic_ai.models import Model
from pydantic_ai.models.openai import OpenAIChatModel

from app.config import get_settings

logger = logging.getLogger("baseflo.agents")


_TEST_MODEL_OVERRIDE: Model | None = None
_MODEL_CACHE: tuple[str, str, Model] | None = None
_AGENT_SEMAPHORE: asyncio.Semaphore | None = None
_AGENT_SEMAPHORE_LIMIT: int | None = None


class AgentRunError(Exception):
    """An agent ran but the typed output did not validate / model errored."""


class AgentsUnavailable(Exception):
    """No model configured (no OPENAI_API_KEY and no test override)."""


def use_test_model(model: Model | None) -> None:
    """Force every agent to use a specific model. Reset by passing None.

    Tests call this with `TestModel()` from `pydantic_ai.models.test` to make
    the pipeline run deterministically without network access.
    """
    global _TEST_MODEL_OVERRIDE, _MODEL_CACHE
    _TEST_MODEL_OVERRIDE = model
    _MODEL_CACHE = None


def agent_is_configured() -> bool:
    if _TEST_MODEL_OVERRIDE is not None:
        return True
    settings = get_settings()
    return settings.openai_api_key is not None


def get_default_model() -> Model:
    """Return the model every agent should use, or raise if unconfigured."""
    if _TEST_MODEL_OVERRIDE is not None:
        return _TEST_MODEL_OVERRIDE
    settings = get_settings()
    if settings.openai_api_key is None:
        raise AgentsUnavailable(
            "No OpenAI key configured. Set OPENAI_API_KEY or call use_test_model() in tests."
        )
    # Ensure the SDK picks up the key without making the caller pass a client.
    key = settings.openai_api_key.get_secret_value()
    os.environ.setdefault("OPENAI_API_KEY", key)
    agent_model = getattr(settings, "openai_agent_model", None) or settings.openai_model
    global _MODEL_CACHE
    if _MODEL_CACHE is not None:
        cached_model_name, cached_key, cached_model = _MODEL_CACHE
        if cached_model_name == agent_model and cached_key == key:
            return cached_model
    model = OpenAIChatModel(agent_model)
    _MODEL_CACHE = (agent_model, key, model)
    return model


def _agent_semaphore() -> asyncio.Semaphore:
    settings = get_settings()
    limit = max(1, int(getattr(settings, "openai_agent_max_concurrency", 1) or 1))
    global _AGENT_SEMAPHORE, _AGENT_SEMAPHORE_LIMIT
    if _AGENT_SEMAPHORE is None or _AGENT_SEMAPHORE_LIMIT != limit:
        _AGENT_SEMAPHORE = asyncio.Semaphore(limit)
        _AGENT_SEMAPHORE_LIMIT = limit
    return _AGENT_SEMAPHORE


def _model_error_message(exc: ModelHTTPError) -> str:
    body = getattr(exc, "body", None)
    if isinstance(body, dict):
        message = body.get("message")
        if isinstance(message, str):
            return message
        error = body.get("error")
        if isinstance(error, dict) and isinstance(error.get("message"), str):
            return error["message"]
    return str(exc)


def _retry_delay_seconds(exc: Exception, *, attempt: int) -> float | None:
    if not isinstance(exc, ModelHTTPError):
        return None
    if exc.status_code not in {408, 409, 429, 500, 502, 503, 504}:
        return None

    settings = get_settings()
    max_delay = float(getattr(settings, "openai_agent_retry_max_seconds", 20.0) or 20.0)
    message = _model_error_message(exc)
    match = re.search(r"try again in\s+([0-9.]+)s", message, flags=re.IGNORECASE)
    if match:
        return min(max_delay, float(match.group(1)) + 0.5)

    base = float(getattr(settings, "openai_agent_retry_base_seconds", 1.0) or 1.0)
    return min(max_delay, base * (2 ** attempt))


async def run_agent(agent: Agent[None, Any], user_message: str, *, label: str) -> Any:
    """Run a Pydantic AI agent and surface a typed AgentRunError on failure.

    The agent's `output_type` already enforces the contract — this wrapper
    only normalises logging and exception type.
    """
    settings = get_settings()
    attempts = max(1, int(getattr(settings, "openai_agent_retry_attempts", 4) or 4))
    last_exc: Exception | None = None
    for attempt in range(attempts):
        try:
            async with _agent_semaphore():
                result = await agent.run(user_message, model=get_default_model())
            return result.output
        except Exception as exc:
            last_exc = exc
            delay = _retry_delay_seconds(exc, attempt=attempt)
            if delay is None or attempt >= attempts - 1:
                if isinstance(exc, ModelHTTPError):
                    logger.warning(
                        "agent.%s failed with model HTTP %s after %s attempt(s): %s",
                        label,
                        exc.status_code,
                        attempt + 1,
                        _model_error_message(exc),
                    )
                else:
                    logger.exception("agent.%s failed", label)
                raise AgentRunError(f"agent {label} failed: {exc}") from exc
            logger.warning(
                "agent.%s hit retryable model error %s; retrying in %.2fs (%s/%s): %s",
                label,
                exc.status_code if isinstance(exc, ModelHTTPError) else type(exc).__name__,
                delay,
                attempt + 1,
                attempts,
                _model_error_message(exc) if isinstance(exc, ModelHTTPError) else exc,
            )
            await asyncio.sleep(delay)

    raise AgentRunError(f"agent {label} failed: {last_exc}")
