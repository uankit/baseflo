"""structlog configuration.

Per docs/40-features/OBSERVABILITY.md, every log line is JSON-emitted (in production)
and auto-tagged from `app.core.context` ContextVars (`tenant_id`, `request_id`,
`job_id`, `agent_run_id`, `agent_name`).

PII scrubbing is wired here as a processor; the active scrub list is injected
per-tenant by the project-version cache. For v1 we ship the scaffolding
with an empty default scrub list.
"""

from __future__ import annotations

import logging
import sys
from typing import Any

import structlog
from structlog.types import EventDict, Processor

from app.core import context as ctx_module
from app.core.config import LogLevel, get_config


def _add_baseflo_context(_logger: object, _method_name: str, event_dict: EventDict) -> EventDict:
    """structlog processor: enrich each event with active context vars."""
    tenant_ctx = ctx_module.try_get_tenant_ctx()
    if tenant_ctx is not None:
        event_dict.setdefault("organization_id", str(tenant_ctx.organization_id))
        event_dict.setdefault("request_id", tenant_ctx.request_id)
        if tenant_ctx.user_id is not None:
            event_dict.setdefault("user_id", str(tenant_ctx.user_id))
    job_id = ctx_module.get_job_id()
    if job_id is not None:
        event_dict.setdefault("job_id", str(job_id))
    agent_run_id = ctx_module.get_agent_run_id()
    if agent_run_id is not None:
        event_dict.setdefault("agent_run_id", str(agent_run_id))
    agent_name = ctx_module.get_agent_name()
    if agent_name is not None:
        event_dict.setdefault("agent_name", agent_name)
    return event_dict


def _scrub_pii(_logger: object, _method_name: str, event_dict: EventDict) -> EventDict:
    """Strip values keyed by known-PII paths.

    v1 ships an empty allowlist; the per-project PII path set is injected later
    once `ColumnClassifier` is producing live classifications.
    """
    return event_dict


def _level_for_config(level: LogLevel) -> int:
    return {
        LogLevel.DEBUG: logging.DEBUG,
        LogLevel.INFO: logging.INFO,
        LogLevel.WARNING: logging.WARNING,
        LogLevel.ERROR: logging.ERROR,
    }[level]


def configure_logging() -> None:
    """Idempotent: safe to call multiple times (tests do)."""
    config = get_config()
    level = _level_for_config(config.log_level)

    timestamper = structlog.processors.TimeStamper(fmt="iso", utc=True)
    shared_processors: list[Processor] = [
        structlog.contextvars.merge_contextvars,
        _add_baseflo_context,
        _scrub_pii,
        structlog.processors.add_log_level,
        timestamper,
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]

    if config.log_json:
        renderer: Processor = structlog.processors.JSONRenderer()
    else:
        renderer = structlog.dev.ConsoleRenderer(colors=sys.stdout.isatty())

    structlog.configure(
        processors=[*shared_processors, renderer],
        wrapper_class=structlog.make_filtering_bound_logger(level),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )

    # Tame stdlib loggers (sqlalchemy, httpx) by routing through structlog.
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=level,
    )
    for noisy in ("sqlalchemy.engine", "httpx", "httpcore", "asyncio"):
        logging.getLogger(noisy).setLevel(max(level, logging.WARNING))


def get_logger(name: str | None = None) -> Any:
    """Return a bound structlog logger. `name` is included as a field."""
    logger = structlog.get_logger()
    if name is not None:
        logger = logger.bind(logger=name)
    return logger
