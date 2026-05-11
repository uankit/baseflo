"""Application settings."""

from __future__ import annotations

from pydantic import Field, PostgresDsn, RedisDsn, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # App
    app_name: str = "Baseflo Brain"
    env: str = Field(default="local", alias="BASEFLO_ENV")
    debug: bool = Field(default=False, alias="BASEFLO_DEBUG")

    # Database
    database_url: PostgresDsn = Field(alias="BASEFLO_DATABASE_URL")
    database_echo: bool = Field(default=False, alias="BASEFLO_DATABASE_ECHO")

    # Redis
    redis_url: RedisDsn = Field(
        default="redis://localhost:6379/0", alias="BASEFLO_REDIS_URL"
    )

    # Auth
    secret_key: SecretStr = Field(alias="BASEFLO_SECRET_KEY")
    access_token_expire_minutes: int = 60 * 24 * 7

    # OpenAI
    openai_api_key: SecretStr | None = Field(
        default=None, alias="OPENAI_API_KEY"
    )
    openai_model: str = Field(default="gpt-4o", alias="OPENAI_MODEL")

    # Google OAuth
    google_client_id: str | None = Field(
        default=None, alias="BASEFLO_GOOGLE_CLIENT_ID"
    )
    google_client_secret: SecretStr | None = Field(
        default=None, alias="BASEFLO_GOOGLE_CLIENT_SECRET"
    )
    google_oauth_redirect_uri: str | None = Field(
        default=None, alias="BASEFLO_GOOGLE_OAUTH_REDIRECT_URI"
    )

    # Frontend URL
    frontend_url: str = Field(
        default="http://localhost:5173", alias="BASEFLO_FRONTEND_URL"
    )


_settings: Settings | None = None


def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings
