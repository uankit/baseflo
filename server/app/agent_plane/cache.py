"""Durable Agent Plane output cache."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from app.db.models import AgentCacheEntry
from app.db.session import open_session


async def load_agent_cache(
    *,
    scope_key: str,
    agent_name: str,
    model_name: str,
    input_hash: str,
) -> dict[str, Any] | None:
    now = datetime.now(UTC)
    async with open_session() as session:
        row = (
            await session.execute(
                select(AgentCacheEntry).where(
                    AgentCacheEntry.scope_key == scope_key,
                    AgentCacheEntry.agent_name == agent_name,
                    AgentCacheEntry.model_name == model_name,
                    AgentCacheEntry.input_hash == input_hash,
                )
            )
        ).scalar_one_or_none()
        if row is None:
            return None
        row.last_used_at = now
        row.hit_count += 1
        return row.output or {}


async def store_agent_cache(
    *,
    scope_key: str,
    agent_name: str,
    model_name: str,
    input_hash: str,
    output: dict[str, Any],
) -> None:
    now = datetime.now(UTC)
    stmt = (
        insert(AgentCacheEntry)
        .values(
            scope_key=scope_key,
            agent_name=agent_name,
            model_name=model_name,
            input_hash=input_hash,
            output=output,
            created_at=now,
            last_used_at=now,
            hit_count=0,
        )
        .on_conflict_do_update(
            constraint="uq_agent_cache_agent_model_input",
            set_={
                "output": output,
                "last_used_at": now,
            },
        )
    )
    async with open_session() as session:
        await session.execute(stmt)
