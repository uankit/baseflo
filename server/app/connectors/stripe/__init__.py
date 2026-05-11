"""Stripe connector.

Per docs/40-features/CONN-STRIPE.md. Importing this module registers the
connector with `ConnectorRegistry`.
"""

from __future__ import annotations

from typing import cast

from app.connectors.base import Connector
from app.connectors.registry import register_connector
from app.connectors.stripe.connector import StripeConnector

# `Connector` is a `@runtime_checkable` Protocol; cast at the boundary so
# mypy is satisfied. The registry verifies structural conformance at runtime.
register_connector(cast(type[Connector], StripeConnector))

__all__ = ["StripeConnector"]
