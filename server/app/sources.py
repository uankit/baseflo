"""Server-side glue for the `connectors` package: instance factory + URLs.

Keep this thin. The factory knows how to wire each connector's runtime with the
credentials it needs from server settings; everything else lives in the
connectors package itself.
"""

from __future__ import annotations

from app.config import get_settings
from app.core.errors import NotFoundError, ValidationError
from connectors import Source, get_source_class

_settings = get_settings()


def get_source_instance(kind: str) -> Source:
    """Create a configured Source instance for the given kind."""
    try:
        cls = get_source_class(kind)
    except Exception as exc:
        raise NotFoundError(
            message=f"Unknown connector kind: {kind}",
            code="UNKNOWN_CONNECTOR",
            status_hint=404,
        ) from exc

    if kind == "google_sheets":
        if not _settings.google_client_id or not _settings.google_client_secret:
            raise ValidationError(
                message="Google OAuth is not configured (set BASEFLO_GOOGLE_CLIENT_ID and BASEFLO_GOOGLE_CLIENT_SECRET)",
                code="GOOGLE_OAUTH_NOT_CONFIGURED",
                status_hint=503,
            )
        return cls(
            client_id=_settings.google_client_id,
            client_secret=_settings.google_client_secret.get_secret_value(),
        )

    if kind == "shopify":
        if not _settings.shopify_client_id or not _settings.shopify_client_secret:
            raise ValidationError(
                message="Shopify OAuth is not configured (set BASEFLO_SHOPIFY_CLIENT_ID and BASEFLO_SHOPIFY_CLIENT_SECRET)",
                code="SHOPIFY_OAUTH_NOT_CONFIGURED",
                status_hint=503,
            )
        scopes = [
            scope.strip()
            for scope in _settings.shopify_scopes.replace(" ", ",").split(",")
            if scope.strip()
        ]
        return cls(
            client_id=_settings.shopify_client_id,
            client_secret=_settings.shopify_client_secret.get_secret_value(),
            api_version=_settings.shopify_api_version,
            scopes=scopes,
            max_rows_per_resource=_settings.shopify_max_rows_per_resource,
        )

    raise NotFoundError(
        message=f"No server-side factory configured for connector '{kind}'",
        code="CONNECTOR_FACTORY_MISSING",
        status_hint=501,
    )


def oauth_callback_url(kind: str) -> str:
    """Public OAuth callback URL for a given connector kind.

    The returned URL must be registered as an authorized redirect URI with the
    OAuth provider. For Google Sheets that means:
        {BASEFLO_API_BASE_URL}/api/v1/oauth/google_sheets/callback
    """
    return f"{_settings.api_base_url.rstrip('/')}/api/v1/oauth/{kind}/callback"
