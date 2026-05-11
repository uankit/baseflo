# `CONN-FRAMEWORK` — Connector Framework + Custom Connector Authoring

Status: M0–M1. The plug-in surface that makes "n connectors + unlimited custom" real. References [`50-design-patterns.md` §2](../50-design-patterns.md) (Adapter pattern + four trust tiers) and [`10-product-dev-users.md` §6](../10-product-dev-users.md) (authoring guide).

---

## 1. Overview

The Connector Framework is the adapter pattern that lets Baseflo speak to any external data source — built-in (Postgres, CSV, Shopify, Stripe, Mailchimp, etc.) or custom (a customer's internal CRM, weird REST API, niche SaaS). The framework defines the contract; each connector is a leaf module that implements it. Capabilities are declared, not assumed; trust tiers determine where the code runs.

The agentic engine and admin UI never know connector internals. They see typed `SourceSchema`, `Row`, `WriteResult`, `Subscription`, `HealthStatus` — same types regardless of which connector is on the other end.

## 2. High-Level Design

```
┌─────────────────────────────────────────────────────┐
│                  Engine + Agents                     │
└────────────────────────┬────────────────────────────┘
                         │ typed: SourceSchema, Row,
                         │        SourceQuery, WriteResult, ...
                         ▼
            ┌─────────────────────────────┐
            │   ConnectorRegistry         │
            │   (name → Connector class)  │
            └─────────────┬───────────────┘
                          │
       ┌──────────────────┼─────────────────┬─────────────────────┐
       ▼                  ▼                 ▼                     ▼
  PostgresConn       ShopifyConn      MyCustomCRMConn       UnknownConn
  (built-in)         (built-in)       (customer-built)      (sandboxed,
                                                             hosted-cloud
                                                             marketplace)
```

Trust tiers (from [`50-design-patterns.md` §2.3](../50-design-patterns.md)):

| Tier | Built by | Where it runs | Sandboxing |
|---|---|---|---|
| Built-in | Baseflo team | In-process | None |
| Verified Marketplace | Community + reviewed | In-process | Code review + signed |
| Self-Host Custom | Customer's eng team | In-process on their infra | They trust their code |
| Hosted Custom (M4+) | Customer or community | Sandboxed worker (isolated process, restricted syscalls, network allowlist) | Strict |

## 3. Low-Level Design

### 3.1 Module Layout

```
server/app/connectors/
├── base.py                  # Connector Protocol + all typed I/O models
├── enums.py                 # AuthKind, ConnectorCapabilities, RowType, etc.
├── registry.py              # ConnectorRegistry singleton; conformance checks
├── testing.py               # ContractTestSuite — every connector inherits to validate
├── sandbox/                 # Hosted-custom worker harness (M4+)
│   ├── runner.py
│   └── policy.py            # network allowlist, timeout, memory cap
└── tests/
    ├── test_protocol_conformance.py
    ├── test_registry.py
    └── test_capability_enforcement.py

server/app/connectors/postgres/
├── __init__.py
├── connector.py             # implements Connector
├── auth.py
├── introspection.py
└── tests/
    └── test_contract.py     # extends ContractTestSuite

server/app/connectors/csv/
├── ...

connectors/                  # top-level for customer-built custom connectors
└── README.md                # "drop your custom connector here for self-host"
```

### 3.2 The Protocol

```python
# server/app/connectors/base.py
from typing import Protocol, AsyncIterator, runtime_checkable
from pydantic import BaseModel

class AuthKind(StrEnum):
    OAUTH2          = "oauth2"
    API_KEY         = "api_key"
    DB_URL          = "db_url"
    FILE_UPLOAD     = "file_upload"
    SERVICE_ACCOUNT = "service_account"
    CUSTOM          = "custom"

class ConnectorCapabilities(BaseModel):
    can_introspect: bool = True
    can_read: bool = True
    can_write: bool = False
    can_subscribe_webhooks: bool = False
    supports_pagination: bool = True
    supports_streaming: bool = False
    requires_periodic_sync: bool = True
    write_back_canonical_only: bool = True

class ConnectorMetadata(BaseModel):
    name: str = Field(pattern=r"^[a-z][a-z0-9_]*$", min_length=2, max_length=64)
    display_name: str
    version: str                    # semver
    protocol_version: str = "1.0"   # framework protocol; engine refuses mismatched majors
    auth_kind: AuthKind
    capabilities: ConnectorCapabilities
    required_scopes: list[str] = []
    optional_scopes: list[str] = []
    icon_url: str | None = None
    docs_url: str | None = None

class AuthCredentials(BaseModel):
    payload: dict[str, str]         # token / api_key / dsn parts; encrypted in flight, validated by connector
    redirect_uri: str | None = None # for OAuth flows

class ConnectorToken(BaseModel):
    connector_name: str
    token_id: UUID                  # primary key in connector_tokens table
    metadata: dict                  # non-secret connection info (e.g., shop domain)

class SourceColumn(BaseModel):
    name: str
    source_type: str                # connector's native type string
    nullable: bool
    sample_values: list[str | int | float | bool | None] = []
    description: str | None = None
    primary_key_member: bool = False

class SourceTable(BaseModel):
    name: str
    columns: list[SourceColumn]
    estimated_row_count: int | None = None
    primary_key: list[str] = []
    description: str | None = None

class SourceSchema(BaseModel):
    tables: list[SourceTable]
    introspected_at: datetime
    notes: str | None = None        # connector-specific caveats

class SourceQuery(BaseModel):
    table: str
    filter: dict | None = None      # connector's native filter expression
    sort: list[str] | None = None
    limit: int | None = None
    cursor: str | None = None       # opaque pagination

class Row(BaseModel):
    values: dict[str, str | int | float | bool | None | list | dict]
    source_id: str | None = None    # the row's id in the source

class SourceMutation(BaseModel):
    table: str
    op: Literal["create", "update", "delete"]
    where: dict | None = None       # required for update/delete
    values: dict | None = None      # required for create/update

class WriteResult(BaseModel):
    success: bool
    affected_rows: int
    new_id: str | None = None
    errors: list[ConnectorError] = []

class Subscription(BaseModel):
    id: str
    events: list[str]
    callback_url: str
    expires_at: datetime | None = None

class HealthStatus(BaseModel):
    healthy: bool
    last_checked_at: datetime
    latency_ms: int
    notes: str | None = None

@runtime_checkable
class Connector(Protocol):
    metadata: ConnectorMetadata

    async def authenticate(self, credentials: AuthCredentials) -> ConnectorToken: ...
    async def revoke(self, token: ConnectorToken) -> None: ...
    async def introspect_schema(self, token: ConnectorToken) -> SourceSchema: ...
    async def sample_rows(self, token: ConnectorToken, table: str, n: int) -> list[Row]: ...
    async def read(self, token: ConnectorToken, query: SourceQuery) -> AsyncIterator[Row]: ...
    async def write(self, token: ConnectorToken, mutation: SourceMutation) -> WriteResult: ...
    async def webhook_subscribe(self, token: ConnectorToken, events: list[str], callback_url: str) -> Subscription: ...
    async def webhook_unsubscribe(self, subscription: Subscription) -> None: ...
    async def health_check(self, token: ConnectorToken) -> HealthStatus: ...
```

### 3.3 The Registry

```python
# server/app/connectors/registry.py
class ConnectorRegistry:
    _connectors: ClassVar[dict[str, type[Connector]]] = {}

    @classmethod
    def register(cls, connector_cls: type[Connector]) -> type[Connector]:
        cls._verify_conformance(connector_cls)
        cls._verify_capability_match(connector_cls)
        if connector_cls.metadata.name in cls._connectors:
            raise BasefloError(error_code="BF-CONN-005", message=f"Duplicate connector: {connector_cls.metadata.name}")
        cls._connectors[connector_cls.metadata.name] = connector_cls
        return connector_cls

    @classmethod
    def get(cls, name: str) -> type[Connector]:
        if name not in cls._connectors:
            raise BasefloError(error_code="BF-CONN-001", message=f"Unknown connector: {name}")
        return cls._connectors[name]

    @classmethod
    def list_available(cls) -> list[ConnectorMetadata]:
        return [cls_.metadata for cls_ in cls._connectors.values()]

    @classmethod
    def _verify_conformance(cls, connector_cls: type) -> None:
        # Runtime protocol check + Pydantic metadata validation.
        if not isinstance(connector_cls, type) or not isinstance(connector_cls(), Connector):
            raise BasefloError(error_code="BF-CONN-006", message="Class does not satisfy Connector protocol.")

    @classmethod
    def _verify_capability_match(cls, connector_cls: type) -> None:
        # If can_write=True, the write method must not be a default no-op.
        # If can_subscribe_webhooks=False, calling webhook_subscribe must raise BF-CONN-002.
        # Static + import-time check.
        ...
```

Built-in connectors register themselves at module import. Custom self-host connectors are loaded via `BASEFLO_CUSTOM_CONNECTORS_PATH` env var; the engine auto-imports modules under that path on boot.

### 3.4 The Contract Test Suite

Every connector — built-in or custom — must pass the same suite. This is what enforces the framework's promise.

```python
# server/app/connectors/testing.py
class ContractTestSuite:
    """Subclass and set class attributes; pytest discovers and runs."""
    connector_cls: ClassVar[type[Connector]]
    test_credentials: ClassVar[AuthCredentials]
    expected_capabilities: ClassVar[set[str]]
    sample_table: ClassVar[str]

    async def test_metadata_complete(self) -> None: ...
    async def test_protocol_version_parses(self) -> None: ...
    async def test_authenticate_with_valid_credentials_returns_token(self) -> None: ...
    async def test_authenticate_with_invalid_credentials_raises_typed_error(self) -> None: ...
    async def test_introspect_schema_returns_non_empty(self) -> None: ...
    async def test_sample_rows_respects_n(self) -> None: ...
    async def test_sample_rows_returns_typed_rows(self) -> None: ...
    async def test_read_paginates(self) -> None: ...
    async def test_read_respects_limit(self) -> None: ...
    async def test_write_returns_typed_result(self) -> None: ...     # only if can_write
    async def test_capability_unsupported_raises_BF_CONN_002(self) -> None: ...
    async def test_health_check_returns_status(self) -> None: ...
    async def test_no_imports_outside_app_connectors_app_core(self) -> None: ...
    async def test_no_module_globals_holding_tenant_state(self) -> None: ...
    async def test_all_errors_are_BasefloError_with_BF_CONN_NNN(self) -> None: ...
```

Built-in connectors run the suite against their real APIs in CI (using sandbox accounts). Custom connectors in self-host must run it locally; `baseflo connector validate <name>` runs it.

### 3.5 Sandboxing for Hosted Custom (M4+)

Hosted-custom connectors run in a separate worker process with:
- Network allowlist (configured per connector at upload).
- CPU and memory caps (cgroup limits).
- Timeout per call (default 30s; per-method override).
- No filesystem access except a per-call temporary directory.
- No shared state with other tenants; the worker is recycled between tenants.

The engine talks to the sandbox via gRPC over a Unix socket. The protocol shape is identical; only the transport differs. Engine code stays oblivious.

## 4. Design Patterns Applied

| Pattern | Where | Why |
|---|---|---|
| **Adapter** | Every `Connector` impl | Each external source becomes a uniform interface. |
| **Registry** | `ConnectorRegistry` | Name-keyed lookup; centralized conformance checks. |
| **Strategy** | Capability flags | Same interface; capabilities determine which calls are valid. |
| **Template Method** | `ContractTestSuite` | Subclass + set class attributes; framework runs the same suite. |
| **Process Boundary** | M4+ hosted-custom sandbox | Same protocol, transport-flexible. |

## 5. Test Plan

- **Framework tests** (`test_protocol_conformance.py`):
  - A class missing a method fails registry registration with `BF-CONN-006`.
  - A class with mismatched capability flags vs. method behavior fails registration with `BF-CONN-007`.
  - `ConnectorRegistry.get(unknown_name)` raises `BF-CONN-001`.
  - Duplicate registration raises `BF-CONN-005`.
- **Per-connector contract tests:** every connector module has its own `tests/test_contract.py` extending `ContractTestSuite`; CI runs them against sandbox accounts (built-ins) or fixtures (custom).
- **Capability enforcement** (`test_capability_enforcement.py`):
  - `webhook_subscribe` on a connector with `can_subscribe_webhooks=False` raises `BF-CONN-002`.
  - `write` on a connector with `can_write=False` raises `BF-CONN-002`.
- **Sandbox tests** (M4+, `test_sandbox.py`):
  - Network calls outside the allowlist are blocked.
  - Filesystem writes outside the temp dir are blocked.
  - Timeout enforcement triggers a typed error.
  - Resource exhaustion (memory/CPU) terminates and reports.

## 6. Error Codes

| Code | Condition | Recovery |
|---|---|---|
| `BF-CONN-001` | Unknown connector requested | UI surfaces "connector not available"; user-facing error. |
| `BF-CONN-002` | Capability not supported by connector | Engine plans around it; admin UI gates feature. |
| `BF-CONN-003` | Token revoked / expired | Admin UI prompts reconnect. |
| `BF-CONN-004` | Source temporarily unavailable | Backoff + retry; health badge degrades. |
| `BF-CONN-005` | Duplicate connector registration | Boot-time error; deployment fails fast. |
| `BF-CONN-006` | Class fails protocol conformance | Boot-time error; deployment fails fast. |
| `BF-CONN-007` | Capability flags don't match implementation | Boot-time error; deployment fails fast. |
| `BF-CONN-008` | Authentication rejected by source | UI prompts re-credential entry. |
| `BF-CONN-009` | Rate limit hit on source | Backoff + retry; surface in admin if persistent. |
| `BF-CONN-010` | Sandbox policy violation | M4+; terminates connector call; sends ops alert. |
| `BF-CONN-011` | Protocol version mismatch | Boot-time fail-fast with clear remediation. |

## 7. Dependencies

- [`IR-CORE`](IR-CORE.md) — connectors produce `SourceSchema`; agents map to `SchemaIR`.
- [`05-coding-rules.md`](../05-coding-rules.md) — no `dict[str, Any]`, no regex/heuristics, layer boundaries.
- [`50-design-patterns.md`](../50-design-patterns.md) — full adapter pattern explanation.

## 8. Milestone

- **M0:** protocol defined; registry implemented; contract test suite shipped; sandbox stubbed.
- **M1:** Postgres + CSV/Excel connectors implemented and pass contract tests in CI.
- **M2:** Google Sheets + (Shopify or Stripe) added.
- **M3:** Notion + Mailchimp + remaining of Shopify/Stripe; **custom-connector authoring path documented and exercised by an internal Toy CRM example**.
- **M4:** sandboxed hosted-custom connector runner; first paying customer deploys a custom connector via the sandbox.
- **M5+:** marketplace surface for community connectors; signed-release verification.
