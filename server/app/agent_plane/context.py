"""Canonical data-plane context builder for agents."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from app.agent_plane.contracts import CanonicalContextPack
from app.agent_plane.store import load_context_pack


async def load_canonical_context(
    organization_id: UUID,
    *,
    snapshot_ids: list[UUID] | None = None,
    include_preview_rows: bool = True,
) -> CanonicalContextPack:
    """Load the compact canonical evidence all agents can safely consume."""
    return await load_context_pack(
        organization_id,
        snapshot_ids=snapshot_ids,
        include_preview_rows=include_preview_rows,
    )


def is_system_field(field: Any) -> bool:
    profile = field.profile if isinstance(field.profile, dict) else {}
    return bool(profile.get("system_column")) or str(field.name).startswith("_bf_")


def context_payload(context: CanonicalContextPack) -> dict[str, Any]:
    return context.model_dump(mode="json")
