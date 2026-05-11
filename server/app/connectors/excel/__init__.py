"""Excel `.xlsx` upload connector.

Per docs/40-features/CONN-EXCEL.md. Importing this module registers the
connector with `ConnectorRegistry`.
"""

from __future__ import annotations

from typing import cast

from app.connectors.base import Connector
from app.connectors.excel.connector import ExcelConnector
from app.connectors.registry import register_connector

# `Connector` is a `@runtime_checkable` Protocol; the registry verifies
# structural conformance at registration. Concrete implementations don't
# inherit from the Protocol, so we cast at the boundary.
register_connector(cast(type[Connector], ExcelConnector))

__all__ = ["ExcelConnector"]
