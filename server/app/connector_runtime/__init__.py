"""Server-side connector runtime boundary."""

from app.connector_runtime.factory import get_source_instance, oauth_callback_url
from app.connector_runtime.oauth import (
    OAuthCallbackError,
    build_authorize_url,
    credentials_from_callback,
)
from app.connector_runtime.resources import resource_config_for
from app.connector_runtime.store import (
    ConnectionRecord,
    DataSourceRecord,
    list_data_sources,
    load_connection,
    load_data_source,
    load_data_sources_by_ids,
    load_source_with_connection,
    mark_data_source_error,
    mark_data_source_synced,
    update_connection_credentials,
    update_data_source_introspection,
    upsert_data_source,
    upsert_oauth_connection,
)

__all__ = [
    "ConnectionRecord",
    "DataSourceRecord",
    "OAuthCallbackError",
    "build_authorize_url",
    "credentials_from_callback",
    "get_source_instance",
    "list_data_sources",
    "load_connection",
    "load_data_source",
    "load_data_sources_by_ids",
    "load_source_with_connection",
    "mark_data_source_error",
    "mark_data_source_synced",
    "oauth_callback_url",
    "resource_config_for",
    "update_connection_credentials",
    "update_data_source_introspection",
    "upsert_data_source",
    "upsert_oauth_connection",
]
