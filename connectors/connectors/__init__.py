import importlib
import pkgutil

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

_CORE_MODULES = {
    "auth",
    "base",
    "errors",
    "registry",
    "spreadsheet_preprocessor",
    "types",
}


def _load_source_modules() -> None:
    """Import connector modules so their @register_source decorators run."""
    for module in pkgutil.iter_modules(__path__):  # type: ignore[name-defined]
        if module.ispkg or module.name in _CORE_MODULES:
            continue
        importlib.import_module(f"{__name__}.{module.name}")


_load_source_modules()

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
