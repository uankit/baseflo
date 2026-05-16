"""Connector resource mapping helpers."""

from __future__ import annotations

from app.connector_runtime.adapters import ResourceLike
from app.connector_runtime.registry import get_connector_runtime


def resource_config_for(kind: str, resource: ResourceLike) -> dict[str, object]:
    """Map a selectable connector resource to persisted DataSource config."""
    return get_connector_runtime(kind).resource_config(resource)
