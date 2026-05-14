from __future__ import annotations

from typing import TYPE_CHECKING

from connectors.errors import ConfigError, ConnectorError

if TYPE_CHECKING:
    from connectors.base import Source, SourceSpec


_registry: dict[str, type["Source"]] = {}


def register_source(cls: type["Source"]) -> type["Source"]:
    """Class decorator. Reads `cls.spec.kind` and stores the class in the registry."""
    spec = getattr(cls, "spec", None)
    if spec is None:
        raise ConfigError(
            message=f"{cls.__name__} must define a `spec` class attribute",
            code="MISSING_SPEC",
        )
    kind = spec.kind
    existing = _registry.get(kind)
    if existing is not None and existing is not cls:
        raise ConfigError(
            message=f"Source kind '{kind}' already registered to {existing.__name__}",
            code="DUPLICATE_KIND",
        )
    _registry[kind] = cls
    return cls


def get_source_class(kind: str) -> type["Source"]:
    cls = _registry.get(kind)
    if cls is None:
        raise ConnectorError(
            message=f"Unknown source kind: {kind}",
            code="UNKNOWN_SOURCE",
            status_hint=400,
        )
    return cls


def get_spec(kind: str) -> "SourceSpec":
    return get_source_class(kind).spec


def list_kinds() -> list[str]:
    return list(_registry.keys())


def list_specs() -> list["SourceSpec"]:
    return [cls.spec for cls in _registry.values()]
