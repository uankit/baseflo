"""Agent Plane runner: model selection, retries, concurrency, and request hashing."""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
import re
from typing import Any

from pydantic import BaseModel
from pydantic_ai.exceptions import ModelHTTPError
from pydantic_ai.models import Model
from pydantic_ai.models.openai import OpenAIChatModel

from app.agent_plane.cache import load_agent_cache, store_agent_cache
from app.agent_plane.factory import AgentFactory
from app.agent_plane.specs import AgentSpec
from app.config import get_settings

logger = logging.getLogger("baseflo.agent_plane")


class AgentPlaneUnavailableError(Exception):
    pass


class AgentPlaneRunError(Exception):
    pass


def canonical_json(value: Any) -> str:
    return json.dumps(value, default=str, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def input_hash(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


class AgentModelProvider:
    def __init__(self, *, model: Model | None = None) -> None:
        self._override = model
        self._cache: tuple[str, str, Model] | None = None

    def model_for(self, spec: AgentSpec) -> Model:
        if self._override is not None:
            return self._override
        settings = get_settings()
        if settings.openai_api_key is None:
            raise AgentPlaneUnavailableError("OPENAI_API_KEY is required for Agent Plane runs")
        key = settings.openai_api_key.get_secret_value()
        os.environ.setdefault("OPENAI_API_KEY", key)
        model_name = spec.model_profile.model_name or settings.openai_agent_model or settings.openai_model
        if self._cache is not None:
            cached_name, cached_key, cached_model = self._cache
            if cached_name == model_name and cached_key == key:
                return cached_model
        model = OpenAIChatModel(model_name)
        self._cache = (model_name, key, model)
        return model

    def cache_key_for(self, spec: AgentSpec) -> str:
        if self._override is not None:
            return f"override:{type(self._override).__name__}"
        settings = get_settings()
        return spec.model_profile.model_name or settings.openai_agent_model or settings.openai_model


class AgentRunner:
    def __init__(
        self,
        *,
        factory: AgentFactory | None = None,
        model_provider: AgentModelProvider | None = None,
    ) -> None:
        self.factory = factory or AgentFactory()
        self.model_provider = model_provider or AgentModelProvider()
        self._semaphores: dict[str, asyncio.Semaphore] = {}
        self._global_semaphore = asyncio.Semaphore(
            max(1, get_settings().openai_agent_max_concurrency)
        )

    def _semaphore_for(self, spec: AgentSpec) -> asyncio.Semaphore:
        existing = self._semaphores.get(spec.name)
        if existing is not None:
            return existing
        semaphore = asyncio.Semaphore(max(1, spec.model_profile.max_parallelism))
        self._semaphores[spec.name] = semaphore
        return semaphore

    async def run(self, spec: AgentSpec, payload: dict[str, Any]) -> BaseModel:
        agent = self.factory.create(spec)
        payload_hash = input_hash(payload)
        cache_scope_key = _cache_scope_key(payload)
        model_cache_key = self.model_provider.cache_key_for(spec)
        if spec.cache_policy.enabled:
            cached = await load_agent_cache(
                scope_key=cache_scope_key,
                agent_name=spec.name,
                model_name=model_cache_key,
                input_hash=payload_hash,
            )
            if cached is not None:
                return spec.output_type.model_validate(cached)
        user_message = (
            f"Run {spec.display_name}.\n"
            f"Input contract: {spec.input_contract}.\n"
            f"Input hash: {payload_hash}.\n"
            f"Payload:\n{canonical_json(payload)}"
        )
        settings = get_settings()
        attempts = max(1, spec.retry_policy.attempts, settings.openai_agent_retry_attempts)
        last_exc: Exception | None = None
        for attempt in range(attempts):
            try:
                async with self._global_semaphore, self._semaphore_for(spec):
                    result = await agent.run(
                        user_message,
                        model=self.model_provider.model_for(spec),
                    )
                output = result.output
                if spec.cache_policy.enabled:
                    await store_agent_cache(
                        scope_key=cache_scope_key,
                        agent_name=spec.name,
                        model_name=model_cache_key,
                        input_hash=payload_hash,
                        output=output.model_dump(mode="json"),
                    )
                return output
            except Exception as exc:
                last_exc = exc
                delay = self._retry_delay(exc, spec=spec, settings=settings, attempt=attempt)
                if delay is None or attempt >= attempts - 1:
                    logger.warning("agent_plane.%s failed: %s", spec.name, exc)
                    raise AgentPlaneRunError(f"{spec.name} failed: {exc}") from exc
                await asyncio.sleep(delay)
        raise AgentPlaneRunError(f"{spec.name} failed: {last_exc}")

    def _retry_delay(
        self,
        exc: Exception,
        *,
        spec: AgentSpec,
        settings: Any,
        attempt: int,
    ) -> float | None:
        if not isinstance(exc, ModelHTTPError):
            return None
        if exc.status_code not in {408, 409, 429, 500, 502, 503, 504}:
            return None
        base_seconds = settings.openai_agent_retry_base_seconds or spec.retry_policy.base_seconds
        max_seconds = settings.openai_agent_retry_max_seconds or spec.retry_policy.max_seconds
        message = _model_error_message(exc)
        match = re.search(r"try again in\s+([0-9.]+)s", message, flags=re.IGNORECASE)
        if match:
            return min(max_seconds, float(match.group(1)) + 0.5)
        return min(max_seconds, base_seconds * (2**attempt))


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


def _cache_scope_key(payload: dict[str, Any]) -> str:
    organization_id = payload.get("organization_id") or payload.get("org_id")
    if organization_id is not None:
        return f"org:{organization_id}"
    return "global"
