"""Connector registry."""

from __future__ import annotations

from typing import Any

from app.connect.base import Connector
from app.core.errors import BasefloError

_registry: dict[str, Connector] = {}


def register(kind: str, connector: Connector) -> None:
    _registry[kind] = connector


def get(kind: str) -> Connector:
    connector = _registry.get(kind)
    if connector is None:
        raise BasefloError(
            message=f"Unknown connector kind: {kind}",
            error_code="BF-CONN-001",
            status_code=400,
        )
    return connector


def list_kinds() -> list[str]:
    return list(_registry.keys())
