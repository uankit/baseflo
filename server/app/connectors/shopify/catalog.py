"""Static catalog of Shopify resources Baseflo exposes.

Per docs/40-features/CONN-SHOPIFY.md §3.3. Shopify's data model is fixed per
API version, so `introspect_schema` returns a deterministic catalog rather
than discovering tables. The agent layer (ColumnClassifier) maps these
connector-native types to semantic + physical types.

Pinned to API version 2026-04.
"""

from __future__ import annotations

from datetime import UTC, datetime

from app.connectors.base import SourceColumn, SourceSchema, SourceTable


__all__ = [
    "API_VERSION",
    "TABLE_NAMES",
    "build_catalog",
    "table_by_name",
]


API_VERSION = "2026-04"


# Connector-native source-type constants. The agent layer turns these into
# `(SemanticType, PhysicalType)` pairs; we keep the strings here so any code
# reading the catalog can pattern-match without magic strings.
_T_GID = "id_gid"          # Shopify GID, e.g. "gid://shopify/Customer/12345"
_T_STR = "string"
_T_TXT = "text"
_T_INT = "integer"
_T_DEC = "decimal"
_T_BOOL = "boolean"
_T_DT = "datetime"
_T_EMAIL = "email"
_T_PHONE = "phone"
_T_JSON = "json"


# Shopify-documented enum values for status-shaped columns. Pinned to the
# `API_VERSION` above; bumping it requires re-checking release notes for additions.
_ORDER_FINANCIAL_STATUS = [
    "pending", "authorized", "partially_paid", "paid",
    "partially_refunded", "refunded", "voided",
]
_ORDER_FULFILLMENT_STATUS = ["fulfilled", "partial", "unfulfilled", "restocked"]
_CUSTOMER_STATE = ["declined", "disabled", "enabled", "invited"]
_PRODUCT_STATUS = ["active", "archived", "draft"]


def _customer_table() -> SourceTable:
    return SourceTable(
        name="customers",
        primary_key=["id"],
        description="Shopify Customer (Admin API 2026-04).",
        columns=[
            SourceColumn(name="id", source_type=_T_GID, nullable=False, primary_key_member=True),
            SourceColumn(name="email", source_type=_T_EMAIL, nullable=True),
            SourceColumn(name="first_name", source_type=_T_STR, nullable=True),
            SourceColumn(name="last_name", source_type=_T_STR, nullable=True),
            SourceColumn(name="phone", source_type=_T_PHONE, nullable=True),
            SourceColumn(name="verified_email", source_type=_T_BOOL, nullable=False),
            SourceColumn(
                name="state",
                source_type=f"enum_CustomerState[{','.join(_CUSTOMER_STATE)}]",
                nullable=False,
            ),
            SourceColumn(name="tags", source_type=_T_JSON, nullable=False),
            SourceColumn(name="note", source_type=_T_TXT, nullable=True),
            SourceColumn(name="orders_count", source_type=_T_INT, nullable=False),
            SourceColumn(name="amount_spent_amount", source_type=_T_DEC, nullable=True),
            SourceColumn(name="amount_spent_currency_code", source_type=_T_STR, nullable=True),
            SourceColumn(name="default_address", source_type=_T_JSON, nullable=True),
            SourceColumn(name="created_at", source_type=_T_DT, nullable=False),
            SourceColumn(name="updated_at", source_type=_T_DT, nullable=False),
        ],
    )


def _order_table() -> SourceTable:
    return SourceTable(
        name="orders",
        primary_key=["id"],
        description="Shopify Order (Admin API 2026-04).",
        columns=[
            SourceColumn(name="id", source_type=_T_GID, nullable=False, primary_key_member=True),
            SourceColumn(name="name", source_type=_T_STR, nullable=False),
            SourceColumn(name="email", source_type=_T_EMAIL, nullable=True),
            SourceColumn(name="phone", source_type=_T_PHONE, nullable=True),
            SourceColumn(name="customer_id", source_type=_T_GID, nullable=True),
            SourceColumn(name="total_price_amount", source_type=_T_DEC, nullable=False),
            SourceColumn(name="total_price_currency_code", source_type=_T_STR, nullable=False),
            SourceColumn(name="subtotal_price_amount", source_type=_T_DEC, nullable=True),
            SourceColumn(name="total_tax_amount", source_type=_T_DEC, nullable=True),
            SourceColumn(
                name="financial_status",
                source_type=f"enum_OrderFinancialStatus[{','.join(_ORDER_FINANCIAL_STATUS)}]",
                nullable=True,
            ),
            SourceColumn(
                name="fulfillment_status",
                source_type=f"enum_OrderFulfillmentStatus[{','.join(_ORDER_FULFILLMENT_STATUS)}]",
                nullable=True,
            ),
            SourceColumn(name="tags", source_type=_T_JSON, nullable=False),
            SourceColumn(name="line_items", source_type=_T_JSON, nullable=False),
            SourceColumn(name="created_at", source_type=_T_DT, nullable=False),
            SourceColumn(name="updated_at", source_type=_T_DT, nullable=False),
            SourceColumn(name="processed_at", source_type=_T_DT, nullable=True),
            SourceColumn(name="cancelled_at", source_type=_T_DT, nullable=True),
        ],
    )


def _product_table() -> SourceTable:
    return SourceTable(
        name="products",
        primary_key=["id"],
        description="Shopify Product (Admin API 2026-04).",
        columns=[
            SourceColumn(name="id", source_type=_T_GID, nullable=False, primary_key_member=True),
            SourceColumn(name="title", source_type=_T_STR, nullable=False),
            SourceColumn(name="handle", source_type=_T_STR, nullable=False),
            SourceColumn(name="product_type", source_type=_T_STR, nullable=True),
            SourceColumn(name="vendor", source_type=_T_STR, nullable=True),
            SourceColumn(
                name="status",
                source_type=f"enum_ProductStatus[{','.join(_PRODUCT_STATUS)}]",
                nullable=False,
            ),
            SourceColumn(name="tags", source_type=_T_JSON, nullable=False),
            SourceColumn(name="description_html", source_type=_T_TXT, nullable=True),
            SourceColumn(name="variants", source_type=_T_JSON, nullable=False),
            SourceColumn(name="total_inventory", source_type=_T_INT, nullable=True),
            SourceColumn(name="created_at", source_type=_T_DT, nullable=False),
            SourceColumn(name="updated_at", source_type=_T_DT, nullable=False),
            SourceColumn(name="published_at", source_type=_T_DT, nullable=True),
        ],
    )


_BUILDERS: tuple[tuple[str, type[SourceTable]] | None, ...] = ()  # silence ruff


_TABLE_BUILDERS = (_customer_table, _order_table, _product_table)
TABLE_NAMES: tuple[str, ...] = ("customers", "orders", "products")


def build_catalog(*, shop_domain: str | None = None) -> SourceSchema:
    """Return the static catalog for this connector's API version.

    `shop_domain` is recorded in `notes` for traceability when the same
    catalog is materialised against multiple shops.
    """
    notes_parts = [f"Shopify Admin API {API_VERSION} catalog."]
    if shop_domain is not None:
        notes_parts.append(f"shop={shop_domain}")
    return SourceSchema(
        tables=[builder() for builder in _TABLE_BUILDERS],
        introspected_at=datetime.now(UTC),
        notes=" ".join(notes_parts),
    )


def table_by_name(name: str) -> SourceTable | None:
    """Lookup helper used by `sample_rows` / `read` to validate the requested table."""
    for builder in _TABLE_BUILDERS:
        table = builder()
        if table.name == name:
            return table
    return None
