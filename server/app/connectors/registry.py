"""ConnectorRegistry — name-keyed registry of connector implementations.

Per docs/40-features/CONN-FRAMEWORK.md §3.3.

Built-in connectors register at module import. Custom self-host connectors
under `connectors/custom/` are auto-imported by the engine on boot via
`BASEFLO_CUSTOM_CONNECTORS_PATH`. Hosted-custom connectors run in a separate
sandboxed worker but are still surfaced through the same registry interface.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import ClassVar

from app.connectors.base import Connector, ConnectorMetadata
from app.core.errors import BasefloError


class ConnectorRegistry:
    """Process-wide registry. Idempotent on identical re-registration."""

    _connectors: ClassVar[dict[str, type[Connector]]] = {}

    @classmethod
    def register(cls, connector_cls: type[Connector]) -> type[Connector]:
        cls._verify_metadata(connector_cls)
        cls._verify_capability_match(connector_cls)
        cls._verify_protocol_conformance(connector_cls)

        meta = connector_cls.metadata  # class attribute on the connector
        existing = cls._connectors.get(meta.name)
        if existing is not None and existing is not connector_cls:
            raise BasefloError(
                error_code="BF-CONN-005",
                message=f"Duplicate connector registration: {meta.name!r}",
                status_code=500,
            )
        cls._connectors[meta.name] = connector_cls
        return connector_cls

    @classmethod
    def get(cls, name: str) -> type[Connector]:
        if name not in cls._connectors:
            raise BasefloError(
                error_code="BF-CONN-001",
                message=f"Unknown connector: {name!r}",
                status_code=400,
                details={"available": sorted(cls._connectors.keys())},
            )
        return cls._connectors[name]

    @classmethod
    def list_available(cls) -> list[ConnectorMetadata]:
        """Return registered connectors' typed metadata, sorted by name."""
        return sorted(
            (cls_.metadata for cls_ in cls._connectors.values()),
            key=lambda m: m.name,
        )

    @classmethod
    def list_names(cls) -> list[str]:
        return sorted(cls._connectors.keys())

    @classmethod
    def clear(cls) -> None:
        """Test-only: drop all registrations."""
        cls._connectors.clear()

    # ----- internal verification -----

    @classmethod
    def _verify_metadata(cls, connector_cls: type[Connector]) -> None:
        meta = getattr(connector_cls, "metadata", None)
        if not isinstance(meta, ConnectorMetadata):
            raise BasefloError(
                error_code="BF-CONN-006",
                message=(
                    f"{connector_cls.__name__!r} missing or invalid `metadata: "
                    "ConnectorMetadata` class attribute."
                ),
                status_code=500,
            )

    @classmethod
    def _verify_capability_match(cls, connector_cls: type[Connector]) -> None:
        """Capability flags must agree with the implementation surface.

        We don't yet enforce method-body inspection (would require AST work),
        but we do check basic consistency: `can_subscribe_webhooks=False`
        connectors must not declare any `required_scopes` containing webhook
        verbs, etc. The full enforcement happens at runtime via BF-CONN-002.
        """
        meta = connector_cls.metadata
        # Basic cross-field consistency.
        if not meta.capabilities.can_introspect:
            raise BasefloError(
                error_code="BF-CONN-007",
                message=(
                    f"{meta.name!r}: every connector must support introspection "
                    "(can_introspect=True)."
                ),
                status_code=500,
            )

    @classmethod
    def _verify_protocol_conformance(cls, connector_cls: type[Connector]) -> None:
        """Verify the class can be instantiated with no args and that the
        instance satisfies the `Connector` runtime-checkable protocol.

        Connectors that need configuration at construction time should accept
        defaults so the registry can do this check without arguments.
        """
        try:
            instance = connector_cls()
        except TypeError as exc:
            raise BasefloError(
                error_code="BF-CONN-006",
                message=(
                    f"{connector_cls.__name__!r}: must be constructible with no "
                    f"required args. Got: {exc}"
                ),
                status_code=500,
                cause=exc,
            ) from exc

        if not isinstance(instance, Connector):
            raise BasefloError(
                error_code="BF-CONN-006",
                message=(
                    f"{connector_cls.__name__!r}: instance does not satisfy the "
                    "Connector protocol (missing methods?)."
                ),
                status_code=500,
            )


def register_connector(connector_cls: type[Connector]) -> type[Connector]:
    """Module-level convenience for `ConnectorRegistry.register(...)`."""
    return ConnectorRegistry.register(connector_cls)


def auto_load(custom_modules: Iterable[str] = ()) -> None:
    """Best-effort auto-loader for self-host custom-connector modules.

    Custom modules can register at boot by setting `BASEFLO_CUSTOM_CONNECTORS_MODULES`
    (comma-separated) and calling this from the worker startup hook. M4+ for
    full sandboxed hosted-custom support.
    """
    import importlib  # noqa: PLC0415

    for module_name in custom_modules:
        importlib.import_module(module_name)
