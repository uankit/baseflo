"""Static catalog of Stripe resources Baseflo exposes.

Per docs/40-features/CONN-STRIPE.md §5. Stripe's data model is fixed per
API version, so `introspect_schema` returns a deterministic catalog rather
than discovering tables.

Pinned to API version 2024-11-20.acacia.
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


API_VERSION = "2024-11-20.acacia"


_T_ID = "id_string"          # Stripe object id, e.g. "cus_NeGfPRiPKxq8jM"
_T_STR = "string"
_T_INT = "integer"
_T_DEC = "decimal"
_T_BOOL = "boolean"
_T_DT = "datetime"
_T_EMAIL = "email"
_T_PHONE = "phone"
_T_JSON = "json"


_SUBSCRIPTION_STATUS = [
    "incomplete", "incomplete_expired", "trialing", "active",
    "past_due", "canceled", "unpaid", "paused",
]
_INVOICE_STATUS = ["draft", "open", "paid", "uncollectible", "void"]
_CHARGE_STATUS = ["pending", "succeeded", "failed"]


def _customer_table() -> SourceTable:
    return SourceTable(
        name="customers",
        primary_key=["id"],
        description="Stripe Customer (API 2024-11-20.acacia).",
        columns=[
            SourceColumn(name="id", source_type=_T_ID, nullable=False, primary_key_member=True),
            SourceColumn(name="email", source_type=_T_EMAIL, nullable=True),
            SourceColumn(name="name", source_type=_T_STR, nullable=True),
            SourceColumn(name="phone", source_type=_T_PHONE, nullable=True),
            SourceColumn(name="description", source_type=_T_STR, nullable=True),
            SourceColumn(name="currency", source_type=_T_STR, nullable=True),
            SourceColumn(name="default_source_id", source_type=_T_STR, nullable=True),
            SourceColumn(name="metadata", source_type=_T_JSON, nullable=False),
            SourceColumn(name="created", source_type=_T_DT, nullable=False),
            SourceColumn(name="test_mode", source_type=_T_BOOL, nullable=False),
        ],
    )


def _subscription_table() -> SourceTable:
    return SourceTable(
        name="subscriptions",
        primary_key=["id"],
        description="Stripe Subscription (API 2024-11-20.acacia).",
        columns=[
            SourceColumn(name="id", source_type=_T_ID, nullable=False, primary_key_member=True),
            SourceColumn(name="customer_id", source_type=_T_ID, nullable=False),
            SourceColumn(
                name="status",
                source_type=f"enum_SubscriptionStatus[{','.join(_SUBSCRIPTION_STATUS)}]",
                nullable=False,
            ),
            SourceColumn(name="current_period_start", source_type=_T_DT, nullable=True),
            SourceColumn(name="current_period_end", source_type=_T_DT, nullable=True),
            SourceColumn(name="cancel_at_period_end", source_type=_T_BOOL, nullable=False),
            SourceColumn(name="canceled_at", source_type=_T_DT, nullable=True),
            SourceColumn(name="latest_invoice_id", source_type=_T_ID, nullable=True),
            SourceColumn(name="plan_amount", source_type=_T_INT, nullable=True),
            SourceColumn(name="plan_currency", source_type=_T_STR, nullable=True),
            SourceColumn(name="plan_interval", source_type=_T_STR, nullable=True),
            SourceColumn(name="items", source_type=_T_JSON, nullable=False),
            SourceColumn(name="created", source_type=_T_DT, nullable=False),
            SourceColumn(name="test_mode", source_type=_T_BOOL, nullable=False),
        ],
    )


def _invoice_table() -> SourceTable:
    return SourceTable(
        name="invoices",
        primary_key=["id"],
        description="Stripe Invoice (API 2024-11-20.acacia).",
        columns=[
            SourceColumn(name="id", source_type=_T_ID, nullable=False, primary_key_member=True),
            SourceColumn(name="customer_id", source_type=_T_ID, nullable=True),
            SourceColumn(name="subscription_id", source_type=_T_ID, nullable=True),
            SourceColumn(
                name="status",
                source_type=f"enum_InvoiceStatus[{','.join(_INVOICE_STATUS)}]",
                nullable=True,
            ),
            SourceColumn(name="amount_due", source_type=_T_INT, nullable=False),
            SourceColumn(name="amount_paid", source_type=_T_INT, nullable=False),
            SourceColumn(name="amount_remaining", source_type=_T_INT, nullable=False),
            SourceColumn(name="currency", source_type=_T_STR, nullable=False),
            SourceColumn(name="paid", source_type=_T_BOOL, nullable=False),
            SourceColumn(name="period_start", source_type=_T_DT, nullable=False),
            SourceColumn(name="period_end", source_type=_T_DT, nullable=False),
            SourceColumn(name="due_date", source_type=_T_DT, nullable=True),
            SourceColumn(name="created", source_type=_T_DT, nullable=False),
            SourceColumn(name="test_mode", source_type=_T_BOOL, nullable=False),
        ],
    )


def _charge_table() -> SourceTable:
    return SourceTable(
        name="charges",
        primary_key=["id"],
        description="Stripe Charge (API 2024-11-20.acacia).",
        columns=[
            SourceColumn(name="id", source_type=_T_ID, nullable=False, primary_key_member=True),
            SourceColumn(name="customer_id", source_type=_T_ID, nullable=True),
            SourceColumn(name="invoice_id", source_type=_T_ID, nullable=True),
            SourceColumn(
                name="status",
                source_type=f"enum_ChargeStatus[{','.join(_CHARGE_STATUS)}]",
                nullable=False,
            ),
            SourceColumn(name="amount", source_type=_T_INT, nullable=False),
            SourceColumn(name="currency", source_type=_T_STR, nullable=False),
            SourceColumn(name="captured", source_type=_T_BOOL, nullable=False),
            SourceColumn(name="paid", source_type=_T_BOOL, nullable=False),
            SourceColumn(name="refunded", source_type=_T_BOOL, nullable=False),
            SourceColumn(name="refunds", source_type=_T_JSON, nullable=False),
            SourceColumn(name="failure_code", source_type=_T_STR, nullable=True),
            SourceColumn(name="failure_message", source_type=_T_STR, nullable=True),
            SourceColumn(name="created", source_type=_T_DT, nullable=False),
            SourceColumn(name="test_mode", source_type=_T_BOOL, nullable=False),
        ],
    )


_TABLE_BUILDERS = (_customer_table, _subscription_table, _invoice_table, _charge_table)
TABLE_NAMES: tuple[str, ...] = ("customers", "subscriptions", "invoices", "charges")


def build_catalog(*, account_id: str | None = None) -> SourceSchema:
    notes_parts = [f"Stripe API {API_VERSION} catalog."]
    if account_id is not None:
        notes_parts.append(f"account={account_id}")
    return SourceSchema(
        tables=[builder() for builder in _TABLE_BUILDERS],
        introspected_at=datetime.now(UTC),
        notes=" ".join(notes_parts),
    )


def table_by_name(name: str) -> SourceTable | None:
    for builder in _TABLE_BUILDERS:
        table = builder()
        if table.name == name:
            return table
    return None
