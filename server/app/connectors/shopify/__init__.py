"""Shopify Admin API connector.

Per docs/40-features/CONN-SHOPIFY.md. Importing this module registers the
connector with `ConnectorRegistry`.
"""

from __future__ import annotations

from typing import cast

from app.connectors.base import Connector
from app.connectors.registry import register_connector
from app.connectors.shopify.connector import ShopifyConnector

# `Connector` is a `@runtime_checkable` Protocol; the registry verifies
# structural conformance at registration. Concrete implementations don't
# inherit from the Protocol (that's the whole point of using Protocol),
# so we cast at the boundary — the runtime check enforces correctness.
register_connector(cast(type[Connector], ShopifyConnector))

__all__ = ["ShopifyConnector"]
