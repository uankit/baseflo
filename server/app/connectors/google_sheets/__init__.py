"""Google Sheets connector.

Per docs/40-features/CONN-SHEETS.md. Importing this module registers the
connector with `ConnectorRegistry`.
"""

from __future__ import annotations

from typing import cast

from app.connectors.base import Connector
from app.connectors.google_sheets.connector import GoogleSheetsConnector
from app.connectors.registry import register_connector

register_connector(cast(type[Connector], GoogleSheetsConnector))

__all__ = ["GoogleSheetsConnector"]
