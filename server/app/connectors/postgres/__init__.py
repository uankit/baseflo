"""Postgres connector.

Per docs/40-features/CONN-PG.md.

Importing this module registers the connector with `ConnectorRegistry`.
"""

from __future__ import annotations

from typing import cast

from app.connectors.base import Connector
from app.connectors.postgres.connector import PostgresConnector
from app.connectors.registry import register_connector

# `Connector` is a `@runtime_checkable` Protocol; the registry verifies
# structural conformance at registration. Concrete implementations don't
# inherit from the Protocol (that's the whole point of using Protocol),
# so we cast at the boundary — the runtime check enforces correctness.
register_connector(cast(type[Connector], PostgresConnector))

__all__ = ["PostgresConnector"]
