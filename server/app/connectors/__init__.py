"""Connector framework + built-in connectors.

Per docs/40-features/CONN-FRAMEWORK.md. Adapter pattern: every external data
source (Postgres, Shopify, CSV, Stripe, custom CRMs, ...) implements the
`Connector` Protocol. The engine and agent layers see only typed I/O models
(`SourceSchema`, `Row`, `WriteResult`, etc.) — never connector internals.

Subpackages register themselves with `ConnectorRegistry` at import.
"""

from __future__ import annotations

from app.connectors.base import (  # noqa: F001
    AuthCredentials,
    AuthKind,
    Connector,
    ConnectorCapabilities,
    ConnectorMetadata,
    ConnectorToken,
    HealthStatus,
    Row,
    SourceColumn,
    SourceMutation,
    SourceQuery,
    SourceSchema,
    SourceTable,
    Subscription,
    WriteResult,
)
from app.connectors.registry import ConnectorRegistry, register_connector  # noqa: F401

# Importing each built-in connector registers it.
from app.connectors import csv as _csv_connector  # noqa: F401, E402
from app.connectors import excel as _excel_connector  # noqa: F401, E402
from app.connectors import google_sheets as _sheets_connector  # noqa: F401, E402
from app.connectors import postgres  # noqa: F401, E402
from app.connectors import shopify as _shopify_connector  # noqa: F401, E402
from app.connectors import stripe as _stripe_connector  # noqa: F401, E402

__all__ = [
    "AuthCredentials",
    "AuthKind",
    "Connector",
    "ConnectorCapabilities",
    "ConnectorMetadata",
    "ConnectorRegistry",
    "ConnectorToken",
    "HealthStatus",
    "Row",
    "SourceColumn",
    "SourceMutation",
    "SourceQuery",
    "SourceSchema",
    "SourceTable",
    "Subscription",
    "WriteResult",
    "register_connector",
]
