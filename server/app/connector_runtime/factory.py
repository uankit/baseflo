"""Connector source factory.

This is the only server module that should instantiate connector sources.
Connector implementations stay in the `connectors` package; server settings and
runtime concerns stay here.
"""

from __future__ import annotations

from connectors import Source, get_source_class

from app.config import get_settings
from app.connector_runtime.registry import get_connector_runtime
from app.core.errors import NotFoundError


def get_source_instance(kind: str) -> Source:
    """Create a configured Source instance for the given connector kind."""
    try:
        get_source_class(kind)
    except Exception as exc:
        raise NotFoundError(
            message=f"Unknown connector kind: {kind}",
            code="UNKNOWN_CONNECTOR",
            status_hint=404,
        ) from exc
    return get_connector_runtime(kind).create_source(get_settings())


def oauth_callback_url(kind: str) -> str:
    settings = get_settings()
    return f"{settings.api_base_url.rstrip('/')}/api/v1/oauth/{kind}/callback"
