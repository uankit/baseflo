from connectors.base import (
    AccountInfo,
    AvailableResource,
    ColumnSchema,
    Row,
    Source,
    SourceQuery,
    SourceSchema,
    SourceSpec,
    TableSchema,
)
from connectors.errors import (
    AuthError,
    ConfigError,
    ConnectorError,
    IntrospectError,
    ReadError,
    WriteError,
)
from connectors.registry import (
    get_source_class,
    get_spec,
    list_kinds,
    list_specs,
    register_source,
)
from connectors.types import AuthMethod, Capability, DataType

# Importing each source module triggers @register_source.
# To add a new source: create connectors/<name>.py with config + SPEC + Source subclass,
# then add one import line here.
from connectors import google_sheets  # noqa: F401, E402
from connectors import shopify  # noqa: F401, E402

__all__ = [
    "AccountInfo",
    "AuthError",
    "AuthMethod",
    "AvailableResource",
    "Capability",
    "ColumnSchema",
    "ConfigError",
    "ConnectorError",
    "DataType",
    "IntrospectError",
    "ReadError",
    "Row",
    "Source",
    "SourceQuery",
    "SourceSchema",
    "SourceSpec",
    "TableSchema",
    "WriteError",
    "get_source_class",
    "get_spec",
    "list_kinds",
    "list_specs",
    "register_source",
]
