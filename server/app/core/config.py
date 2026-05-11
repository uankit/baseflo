"""Pydantic-settings-backed configuration.

All configuration comes from env vars (or `.env`) — never from CLI flags or code constants.
See `.env.example` for the full list.
"""

from __future__ import annotations

from enum import StrEnum
from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Environment(StrEnum):
    LOCAL = "local"
    STAGING = "staging"
    PRODUCTION = "production"


class LogLevel(StrEnum):
    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


class AgentProvider(StrEnum):
    OPENAI = "openai"
    ANTHROPIC = "anthropic"  # env-flip switch path per docs/00-decisions.md §7B


class KMSProvider(StrEnum):
    LOCAL = "local"
    AWS_KMS = "aws_kms"


class AppConfig(BaseSettings):
    """Top-level application configuration.

    Validated at startup. Missing required fields fail fast with a clear message.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_prefix="",
        extra="ignore",
        case_sensitive=False,
    )

    # ----- App -----
    env: Environment = Field(default=Environment.LOCAL, alias="BASEFLO_ENV")
    log_level: LogLevel = Field(default=LogLevel.INFO, alias="BASEFLO_LOG_LEVEL")
    log_json: bool = Field(default=False, alias="BASEFLO_LOG_JSON")
    api_base_url: str = Field(default="http://localhost:8000", alias="BASEFLO_API_BASE_URL")
    web_base_url: str = Field(default="http://localhost:5173", alias="BASEFLO_WEB_BASE_URL")
    request_id_header: str = Field(default="X-Request-ID", alias="BASEFLO_REQUEST_ID_HEADER")

    # ----- Database -----
    database_url: str = Field(alias="BASEFLO_DATABASE_URL")
    database_pool_size: int = Field(default=10, alias="BASEFLO_DATABASE_POOL_SIZE", ge=1, le=200)
    database_max_overflow: int = Field(
        default=20, alias="BASEFLO_DATABASE_MAX_OVERFLOW", ge=0, le=400
    )

    # ----- Redis -----
    redis_url: str = Field(alias="BASEFLO_REDIS_URL")

    # ----- LLM provider (per docs/00-decisions.md §7B) -----
    agent_provider: AgentProvider = Field(default=AgentProvider.OPENAI, alias="BASEFLO_AGENT_PROVIDER")
    openai_api_key: SecretStr | None = Field(default=None, alias="OPENAI_API_KEY")
    anthropic_api_key: SecretStr | None = Field(default=None, alias="ANTHROPIC_API_KEY")
    agent_fast_model_name: str = Field(
        default="gpt-4.1-mini", alias="BASEFLO_AGENT_FAST_MODEL_NAME"
    )
    agent_balanced_model_name: str = Field(
        default="gpt-4.1", alias="BASEFLO_AGENT_BALANCED_MODEL_NAME"
    )
    agent_reasoning_model_name: str = Field(
        default="o3-mini", alias="BASEFLO_AGENT_REASONING_MODEL_NAME"
    )
    agent_max_concurrency: int = Field(
        default=4, alias="BASEFLO_AGENT_MAX_CONCURRENCY", ge=1, le=64
    )
    agent_max_repair_attempts: int = Field(
        default=2, alias="BASEFLO_AGENT_MAX_REPAIR_ATTEMPTS", ge=1, le=5
    )

    # ----- Auth -----
    session_cookie_name: str = Field(default="baseflo_session", alias="BASEFLO_SESSION_COOKIE_NAME")
    session_cookie_secure: bool = Field(default=False, alias="BASEFLO_SESSION_COOKIE_SECURE")
    session_ttl_days: int = Field(default=30, alias="BASEFLO_SESSION_TTL_DAYS", ge=1, le=365)
    secret_key: SecretStr = Field(alias="BASEFLO_SECRET_KEY")

    # ----- KMS -----
    kms_provider: KMSProvider = Field(default=KMSProvider.LOCAL, alias="BASEFLO_KMS_PROVIDER")
    local_kek_base64: SecretStr | None = Field(default=None, alias="BASEFLO_LOCAL_KEK_BASE64")
    aws_kms_key_arn: str | None = Field(default=None, alias="BASEFLO_AWS_KMS_KEY_ARN")
    aws_region: str | None = Field(default=None, alias="AWS_REGION")

    shopify_client_id: str | None = Field(default=None, alias="BASEFLO_SHOPIFY_CLIENT_ID")
    shopify_client_secret: SecretStr | None = Field(
        default=None, alias="BASEFLO_SHOPIFY_CLIENT_SECRET"
    )
    shopify_api_version: str = Field(
        default="2026-04", alias="BASEFLO_SHOPIFY_API_VERSION"
    )

    google_client_id: str | None = Field(default=None, alias="BASEFLO_GOOGLE_CLIENT_ID")
    google_client_secret: SecretStr | None = Field(
        default=None, alias="BASEFLO_GOOGLE_CLIENT_SECRET"
    )

    stripe_webhook_secret: SecretStr | None = Field(
        default=None, alias="BASEFLO_STRIPE_WEBHOOK_SECRET"
    )
    stripe_api_version: str = Field(
        default="2024-11-20.acacia", alias="BASEFLO_STRIPE_API_VERSION"
    )

    digest_email_from: str = Field(
        default="digest@baseflo.local", alias="BASEFLO_DIGEST_EMAIL_FROM"
    )
    digest_resend_api_key: SecretStr | None = Field(
        default=None, alias="BASEFLO_DIGEST_RESEND_API_KEY"
    )
    digest_resend_endpoint: str = Field(
        default="https://api.resend.com/emails",
        alias="BASEFLO_DIGEST_RESEND_ENDPOINT",
    )

    # ----- Observability -----
    otel_enabled: bool = Field(default=False, alias="BASEFLO_OTEL_ENABLED")
    otel_exporter_otlp_endpoint: str | None = Field(
        default=None, alias="BASEFLO_OTEL_EXPORTER_OTLP_ENDPOINT"
    )
    sentry_dsn: str | None = Field(default=None, alias="BASEFLO_SENTRY_DSN")
    sentry_traces_sample_rate: float = Field(
        default=0.1, alias="BASEFLO_SENTRY_TRACES_SAMPLE_RATE", ge=0.0, le=1.0
    )

    # ----- Validators -----
    @field_validator("database_url")
    @classmethod
    def _require_async_driver(cls, v: str) -> str:
        if not v.startswith(("postgresql+asyncpg://", "postgres+asyncpg://")):
            raise ValueError(
                "BASEFLO_DATABASE_URL must use the asyncpg driver "
                "(postgresql+asyncpg://...). See .env.example."
            )
        return v

    def is_production_like(self) -> bool:
        return self.env in {Environment.STAGING, Environment.PRODUCTION}

    def model_name_for_tier(self, tier: Literal["fast", "balanced", "reasoning"]) -> str:
        if tier == "fast":
            return self.agent_fast_model_name
        if tier == "balanced":
            return self.agent_balanced_model_name
        return self.agent_reasoning_model_name


@lru_cache(maxsize=1)
def get_config() -> AppConfig:
    """Cached config accessor.

    First call loads & validates env; subsequent calls return the cached instance.
    Tests that need to override values should use the `override_config` test fixture.
    """
    return AppConfig()  # pydantic-settings reads from env at construction
