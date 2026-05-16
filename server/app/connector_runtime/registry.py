"""Runtime adapter registry for server-side connector wiring."""

from __future__ import annotations

from connectors import get_source_class

from app.connector_runtime.adapters import (
    ConnectorRuntimeAdapter,
    DefaultConnectorRuntimeAdapter,
    GoogleSheetsRuntimeAdapter,
    ShopifyRuntimeAdapter,
)
from app.core.errors import NotFoundError

_ADAPTERS: dict[str, ConnectorRuntimeAdapter] = {
    GoogleSheetsRuntimeAdapter.kind: GoogleSheetsRuntimeAdapter(),
    ShopifyRuntimeAdapter.kind: ShopifyRuntimeAdapter(),
}


def get_connector_runtime(kind: str) -> ConnectorRuntimeAdapter:
    adapter = _ADAPTERS.get(kind)
    if adapter is not None:
        return adapter
    try:
        get_source_class(kind)
    except Exception as exc:
        raise NotFoundError(
            message=f"Unknown connector kind: {kind}",
            code="UNKNOWN_CONNECTOR",
            status_hint=404,
        ) from exc
    return DefaultConnectorRuntimeAdapter(kind)


def register_connector_runtime(adapter: ConnectorRuntimeAdapter) -> None:
    _ADAPTERS[adapter.kind] = adapter
