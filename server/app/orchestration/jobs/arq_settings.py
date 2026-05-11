"""arq worker configuration.

Run a worker locally with:

    arq app.orchestration.jobs.arq_settings.WorkerSettings

Per docs/40-features/JOBS-AND-SSE.md §3.2 — idempotency-key support, retries
with exponential backoff, DLQ for terminal failures.
"""

from __future__ import annotations

from typing import Any

from arq.connections import RedisSettings

from app.core.config import get_config
from app.observability.logging import configure_logging, get_logger
from app.orchestration.jobs.tasks.generate import run_generation_job

logger = get_logger("worker")


def _redis_settings() -> RedisSettings:
    return RedisSettings.from_dsn(get_config().redis_url)


async def on_startup(ctx: dict[str, Any]) -> None:
    configure_logging()
    logger.info("worker_started")


async def on_shutdown(ctx: dict[str, Any]) -> None:
    logger.info("worker_shutting_down")


class WorkerSettings:
    """arq WorkerSettings entrypoint."""

    functions = [run_generation_job]
    redis_settings = _redis_settings()
    on_startup = on_startup
    on_shutdown = on_shutdown
    max_jobs = 10
    job_timeout = 600          # 10-minute hard ceiling per job
    max_tries = 5              # exponential backoff handled by arq
    keep_result = 3600         # hold completed-job results 1h
    poll_delay = 0.5
