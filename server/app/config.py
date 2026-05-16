"""Application settings — loaded from environment / .env."""

from __future__ import annotations

from pydantic import Field, PostgresDsn, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # App
    app_name: str = "Baseflo"
    env: str = Field(default="local", alias="BASEFLO_ENV")

    # Database
    database_url: PostgresDsn = Field(alias="BASEFLO_DATABASE_URL")
    database_echo: bool = Field(default=False, alias="BASEFLO_DATABASE_ECHO")

    # Auth
    secret_key: SecretStr = Field(alias="BASEFLO_SECRET_KEY")

    # Google OAuth (for the google_sheets connector)
    google_client_id: str | None = Field(
        default=None, alias="BASEFLO_GOOGLE_CLIENT_ID"
    )
    google_client_secret: SecretStr | None = Field(
        default=None, alias="BASEFLO_GOOGLE_CLIENT_SECRET"
    )

    # Shopify OAuth / Admin API
    shopify_client_id: str | None = Field(
        default=None, alias="BASEFLO_SHOPIFY_CLIENT_ID"
    )
    shopify_client_secret: SecretStr | None = Field(
        default=None, alias="BASEFLO_SHOPIFY_CLIENT_SECRET"
    )
    shopify_api_version: str = Field(
        default="2026-04", alias="BASEFLO_SHOPIFY_API_VERSION"
    )
    shopify_scopes: str = Field(
        default=(
            "read_analytics,read_assigned_fulfillment_orders,read_customer_events,"
            "read_all_cart_transforms,read_validations,read_cash_tracking,"
            "read_checkout_branding_settings,read_checkouts,"
            "read_custom_fulfillment_services,read_customers,read_customer_merge,"
            "read_price_rules,read_discounts,read_discovery,read_draft_orders,"
            "read_fulfillments,read_gift_card_transactions,read_gift_cards,"
            "read_inventory,read_inventory_shipments,"
            "read_inventory_shipments_received_items,read_inventory_transfers,"
            "read_locations,read_marketing_integrated_campaigns,"
            "read_marketing_events,read_merchant_managed_fulfillment_orders,"
            "read_orders,read_payment_terms,read_product_listings,read_products,"
            "read_returns,read_shipping,read_content,"
            "read_third_party_fulfillment_orders,customer_read_companies,"
            "customer_read_draft_orders,customer_read_markets,customer_read_orders,"
            "customer_read_quick_sale"
        ),
        alias="BASEFLO_SHOPIFY_SCOPES",
    )
    shopify_max_rows_per_resource: int = Field(
        default=5000, alias="BASEFLO_SHOPIFY_MAX_ROWS_PER_RESOURCE"
    )

    # URLs
    api_base_url: str = Field(
        default="http://localhost:8000", alias="BASEFLO_API_BASE_URL"
    )
    frontend_url: str = Field(
        default="http://localhost:5173", alias="BASEFLO_FRONTEND_URL"
    )

    # Canonical data storage (DuckDB per-org files live under {data_dir}/duckdb/)
    data_dir: str = Field(default="./data", alias="BASEFLO_DATA_DIR")

    # Agent model settings
    openai_api_key: SecretStr | None = Field(default=None, alias="OPENAI_API_KEY")
    openai_model: str = Field(default="gpt-4o-mini", alias="BASEFLO_OPENAI_MODEL")
    openai_agent_model: str | None = Field(
        default="gpt-4o",
        alias="BASEFLO_OPENAI_AGENT_MODEL",
    )
    openai_agent_max_concurrency: int = Field(
        default=1,
        alias="BASEFLO_OPENAI_AGENT_MAX_CONCURRENCY",
    )
    openai_agent_retry_attempts: int = Field(
        default=4,
        alias="BASEFLO_OPENAI_AGENT_RETRY_ATTEMPTS",
    )
    openai_agent_retry_base_seconds: float = Field(
        default=1.0,
        alias="BASEFLO_OPENAI_AGENT_RETRY_BASE_SECONDS",
    )
    openai_agent_retry_max_seconds: float = Field(
        default=20.0,
        alias="BASEFLO_OPENAI_AGENT_RETRY_MAX_SECONDS",
    )


_settings: Settings | None = None


def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings()  # type: ignore[call-arg]
    return _settings
