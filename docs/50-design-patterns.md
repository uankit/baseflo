# Baseflo — Design Patterns

Status: locked. This document specifies the core patterns the codebase uses, where each is applied, and the rules that govern them. Per-feature docs in `40-features/` reference back to this doc.

The bar: patterns serve the architecture; they are not invoked for cleverness. Every use of a pattern must be justified by a constraint. The goal is *legibility*: a new contributor should look at any module and know exactly what pattern it expresses and why.

---

## 1. Pattern Index

| Pattern | Used for | Where |
|---|---|---|
| **Adapter** | Connector framework — every external source is an adapter conforming to the `Connector` protocol. | `app/connectors/` |
| **Strategy** | Deployment mode runners — same engine, four runners (`HostedDataPlane`, `BYODataPlane`, `SelfHostDataPlane`, `LocalDataPlane`). | `app/engines/data_plane/` |
| **Factory** | Agent provider — builds Pydantic AI `Agent` instances from `AgentSpec` declarations. | `app/agents/runtime.py`, `app/agents/registry.py` |
| **Repository** | Database access — services never touch SQLAlchemy sessions directly. | `app/repositories/` |
| **Command** | Refinements — every refinement is a typed command producing a typed change plan and an immutable child version. | `app/services/refinement.py` |
| **Observer / Pub-Sub** | SSE event stream — Postgres `LISTEN/NOTIFY` decouples emitters from subscribers. | `app/conversation/sse.py`, `app/orchestration/events.py` |
| **Singleton** | Config and KMS clients — one instance per process, lazy-loaded. | `app/core/config.py`, `app/core/crypto.py` |
| **Registry** | Agent and connector lookup — both are name-keyed, populated at import. | `app/agents/registry.py`, `app/connectors/registry.py` |
| **Specification** | Filtering and search — typed predicate objects compiled to SQL by repositories. | `app/repositories/_specs.py` |
| **Pipe / Functional Composition** | Schema IR transformations — small typed steps composed into a typed pipeline. | `app/engines/schema/transforms.py` |
| **Gate (typed pre-condition)** | `CoherenceGate` — terminal node returns `passed: bool` + `repair_routes: list[RepairRoute]`. | `app/agents/specialists/coherence_gate.py` |
| **Saga / Compensating Action** | Long-running multi-step flows (refinements, re-introspection) — every step has a compensator. | `app/orchestration/sagas.py` |
| **Evidence-Feeding** | Deterministic helper computes typed facts; agent reasons over them. The load-bearing pattern that makes agentic-but-not-wrapper real. | `app/agents/specialists/*/overlap.py`, `app/agents/specialists/coherence_gate/checks.py` |

What we are explicitly **not** using:

- ❌ **God-objects.** A "Manager" that does ten unrelated things is forbidden. Managers coordinate; they don't implement.
- ❌ **Mixin-based "smart" base classes.** Composition over inheritance.
- ❌ **Service locators.** Dependency injection at construction; no global state lookups.
- ❌ **Active Record.** ORM models are dumb data containers; behavior lives in services + engines.
- ❌ **Magic decorators that hide control flow.** Decorators are allowed for cross-cutting concerns (`@register_agent`, `@async_retry`) but never for business logic.

---

## 2. Adapter — The Connector Framework

The connector framework is the most important pattern in the system because customer extensibility runs through it. There can be **N built-in connectors and unlimited custom connectors** built by users against our published spec — for internal CRMs, custom databases, niche SaaS, anything.

### 2.1 The Connector Protocol

```python
# app/connectors/base.py
from typing import Protocol, AsyncIterator, runtime_checkable
from pydantic import BaseModel

class ConnectorMetadata(BaseModel):
    name: str                        # stable identifier ("postgres", "shopify", "my_internal_crm")
    display_name: str
    version: str                     # semver
    auth_kind: AuthKind              # OAUTH2 | API_KEY | DB_URL | FILE_UPLOAD | SERVICE_ACCOUNT | CUSTOM
    capabilities: ConnectorCapabilities  # flags: can_introspect, can_read, can_write, can_subscribe_webhooks, supports_pagination, ...
    required_scopes: list[str]
    optional_scopes: list[str]

@runtime_checkable
class Connector(Protocol):
    metadata: ConnectorMetadata

    async def authenticate(self, credentials: AuthCredentials) -> ConnectorToken: ...
    async def revoke(self, token: ConnectorToken) -> None: ...

    async def introspect_schema(self, token: ConnectorToken) -> SourceSchema: ...
    async def sample_rows(self, token: ConnectorToken, table: str, n: int) -> list[Row]: ...

    async def read(self, token: ConnectorToken, query: SourceQuery) -> AsyncIterator[Row]: ...
    async def write(self, token: ConnectorToken, mutation: SourceMutation) -> WriteResult: ...

    async def webhook_subscribe(
        self, token: ConnectorToken, events: list[str], callback_url: str
    ) -> Subscription: ...
    async def webhook_unsubscribe(self, subscription: Subscription) -> None: ...

    async def health_check(self, token: ConnectorToken) -> HealthStatus: ...
```

Every input and output is a strongly-typed Pydantic model — no `dict[str, Any]`. The protocol is `runtime_checkable` so the registry can verify conformance at import time.

### 2.2 The Registry

```python
# app/connectors/registry.py
from app.connectors.base import Connector

class ConnectorRegistry:
    _connectors: dict[str, type[Connector]] = {}

    @classmethod
    def register(cls, connector_cls: type[Connector]) -> type[Connector]:
        cls._verify_conformance(connector_cls)
        cls._connectors[connector_cls.metadata.name] = connector_cls
        return connector_cls

    @classmethod
    def get(cls, name: str) -> type[Connector]:
        if name not in cls._connectors:
            raise BasefloError(error_code="BF-CONN-001", message=f"Unknown connector: {name}")
        return cls._connectors[name]

    @classmethod
    def _verify_conformance(cls, connector_cls: type[Connector]) -> None:
        # Static + runtime checks: protocol satisfied, metadata valid, semver parses, etc.
        ...

# Each connector module ends with:
# ConnectorRegistry.register(PostgresConnector)
```

Built-in connectors register at server boot. Custom connectors register the same way; the difference is *where the module lives* and *how strictly we trust it*.

### 2.3 Trust Tiers for Custom Connectors

| Tier | Who builds it | Where it runs | Sandboxing |
|---|---|---|---|
| **Built-in** | Baseflo team | In-process | None (we trust ourselves). |
| **Verified Marketplace** | Community + reviewed by us (M5+) | In-process | Code review + signed releases. |
| **Self-Host Custom** | Customer's engineering team | In-process on their infra | They trust their own code. |
| **Hosted Custom** (M4+) | Customer pays us to build, or community | Sandboxed worker (separate process, restricted syscalls, network allowlist) | Strict; the connector never sees other tenants. |

### 2.4 Building a Custom Connector — The Documented Path

This is what a customer-facing developer guide will say (full version in `docs/10-product-dev-users.md`). Process:

1. **Scaffold:** `baseflo connector init my_internal_crm` creates a module with the protocol stubs filled in and a sample `tests/` folder.
2. **Implement:** fill in the seven required methods. Each has a typed signature that your editor + `mypy --strict` check.
3. **Test:** the scaffold ships with contract tests (`pytest tests/`). All connectors — built-in or custom — must pass the same suite.
4. **Validate locally:** run `baseflo dev` and connect your custom source; the local engine treats it identically to a built-in connector.
5. **Ship:** for self-host, drop the module into `connectors/custom/`; the registry picks it up at boot. For hosted custom, package as a distribution; we deploy to a sandboxed worker.

The protocol never changes for custom connectors. Anything they need to do — auth, introspection, paging, write-back — lives inside the seven methods. If a feature requires changes to the protocol, that's a Baseflo team change with a versioned protocol bump, not a customer-side hack.

### 2.5 Capability Discovery

Not every connector supports every operation. A static CSV upload can't `write` or `webhook_subscribe`. The `ConnectorCapabilities` flags let the engine know what's supported, and the admin UI gates features accordingly:

```python
class ConnectorCapabilities(BaseModel):
    can_introspect: bool = True
    can_read: bool = True
    can_write: bool = False
    can_subscribe_webhooks: bool = False
    supports_pagination: bool = True
    supports_streaming: bool = False
    requires_periodic_sync: bool = True
    write_back_canonical_only: bool = True   # i.e., agent-decided authoritative source
```

Capabilities are part of `ConnectorMetadata`, so the engine plans work around what's possible. Any operation requested against a connector that lacks the capability raises `BF-CONN-002` immediately.

### 2.6 Anti-Patterns

- ❌ A connector module that imports from `app/engines/` or `app/agents/`. Connectors are leaves.
- ❌ A connector that returns `dict` instead of typed `Row` / `SourceSchema`.
- ❌ A connector that throws untyped exceptions; every failure is a `BasefloError` with `BF-CONN-NNN`.
- ❌ A connector that holds tenant context in module-level globals.
- ❌ A connector that calls the LLM. Connectors are deterministic; if a connector wants to "infer" something, it returns raw data and the agent layer infers.

---

## 3. Strategy — Deployment Mode Runners

Same engine code, four runners. Selected at runtime by `Project.deployment_mode`.

```python
# app/engines/data_plane/base.py
class DataPlane(Protocol):
    async def emit_ddl(self, schema_ir: SchemaIR, tenant: TenantCtx) -> EmissionResult: ...
    async def query(self, plan: QueryPlan, tenant: TenantCtx) -> AsyncIterator[Row]: ...
    async def write(self, mutation: Mutation, tenant: TenantCtx) -> WriteResult: ...
    async def execute_kpi(self, kpi: KPIDefinition, tenant: TenantCtx) -> KPIResult: ...
    async def health(self, tenant: TenantCtx) -> HealthStatus: ...

# Implementations:
#   app/engines/data_plane/hosted.py         — multi-tenant Postgres on our infra
#   app/engines/data_plane/byo_db.py         — customer's Postgres connection
#   app/engines/data_plane/self_host.py      — bundled Postgres on customer infra
#   app/engines/data_plane/local_dev.py      — docker-compose Postgres for `baseflo dev`
```

The factory selects:

```python
def make_data_plane(mode: DeploymentMode, project: Project) -> DataPlane:
    match mode:
        case DeploymentMode.HOSTED:    return HostedDataPlane(...)
        case DeploymentMode.BYO_DB:    return BYODataPlane(project.tenant_data_dsn)
        case DeploymentMode.SELF_HOST: return SelfHostDataPlane(...)
        case DeploymentMode.LOCAL_DEV: return LocalDataPlane(...)
```

Engine and agent code never branch on deployment mode. They call `data_plane.query(...)` and the strategy does the right thing.

---

## 4. Factory — Agent Provider

The agent registry uses a factory to construct Pydantic AI `Agent` instances on demand, cached by configuration:

```python
# app/agents/runtime.py (excerpt)
@lru_cache(maxsize=256)
def _build_agent(
    agent_name: str,
    model_name: str,
    output_schema_hash: str,
    instructions_hash: str,
) -> pydantic_ai.Agent:
    spec = AgentRegistry.get(agent_name)
    return pydantic_ai.Agent(
        model=resolve_provider(model_name),
        output_type=spec.output_type,
        instructions=spec.instructions,
        retries=spec.max_repair_attempts,
    )
```

The cache key is the *configuration*, not the agent identity, so a tier escalation rebuilds with the new model but reuses the same prompt hash.

---

## 5. Repository — Database Access

Per `05-coding-rules.md` §3.2, services never touch `Session` directly.

```python
# app/repositories/projects.py
class ProjectRepository:
    def __init__(self, session: AsyncSession, tenant_id: UUID):
        self._session = session
        self._tenant_id = tenant_id

    async def get(self, project_id: UUID) -> Project:
        # SQL is built here; tenant scoping is enforced by RLS + session var
        ...

    async def list_for_workspace(self, workspace_id: UUID) -> list[Project]:
        ...

    async def create(self, draft: ProjectDraft) -> Project:
        ...
```

Constructed by FastAPI dependency injection per request:

```python
async def get_project_repo(
    session: AsyncSession = Depends(get_session),
    tenant: TenantCtx = Depends(get_tenant_ctx),
) -> ProjectRepository:
    return ProjectRepository(session, tenant.organization_id)
```

Specifications (`Spec` objects) are passed for filtering instead of building queries inline:

```python
projects = await repo.list(spec=ProjectSpec(active=True, created_after=last_week))
```

The repository compiles `Spec` to SQL; the service stays declarative.

---

## 6. Command — Refinements

Every refinement is a typed command. Idempotency, audit, and rollback all hang off this shape.

```python
# app/services/refinement.py
class RefineProjectCommand(BaseModel):
    project_id: UUID
    parent_version_id: UUID
    intent_text: str
    actor: ActorRef
    idempotency_key: str

class RefineProjectResult(BaseModel):
    refinement_id: UUID
    child_version_id: UUID | None
    change_plan: ChangePlan
    impact_summary: ImpactSummary
    status: RefinementStatus

class RefinementService:
    async def execute(self, command: RefineProjectCommand) -> RefineProjectResult:
        # 1. Run IntentInterpreter -> ImpactAnalyzer -> ChangePlanner.
        # 2. Apply plan deterministically into child IR.
        # 3. Run CoherenceGate; on fail, route repair.
        # 4. Persist child version atomically.
        # 5. Audit-log the command + result.
        ...
```

Properties:
- **Idempotent.** Same `idempotency_key` returns the same result.
- **Auditable.** Command + result are persisted in `refinements` and `audit_events`.
- **Reversible.** Child version is immutable; rollback is "set `current_version_id` back to parent."
- **Replayable.** A future feature can replay a sequence of refinements onto a fresh schema and assert the same final state.

---

## 7. Observer / Pub-Sub — SSE Event Stream

Postgres `LISTEN/NOTIFY` is the backbone. Why: we already have Postgres; it's multi-instance safe; one less service in the failure domain.

```python
# Emit
async def emit_event(conversation_id: UUID, event: ConversationEvent) -> None:
    seq = await events_repo.append(conversation_id, event)
    await session.execute(text(f"NOTIFY conversation_{conversation_id}, '{seq}'"))

# Subscribe (one connection per SSE client)
async def stream(conversation_id: UUID) -> AsyncIterator[bytes]:
    async with listen(f"conversation_{conversation_id}") as channel:
        async for notification in channel:
            seq = int(notification.payload)
            event = await events_repo.get_by_seq(conversation_id, seq)
            yield format_sse(event)
```

The events are persisted first; clients can resume from a sequence number on reconnect. This is the "observer + replay" combination — observers see new events, but the past is never lost.

---

## 8. Gate — `CoherenceGate`

The single permitted form of cross-agent loops in the system. Defined fully in `03-agentic-workflow.md`. Pattern shape:

```python
class GateOutput(BaseModel):
    passed: bool
    issues: list[StructuredIssue]
    repair_routes: list[RepairRoute]
    escalate_to_user: ClarificationRequest | None
```

The manager's loop:

```python
for cycle in range(MAX_REPAIR_CYCLES):  # MAX_REPAIR_CYCLES = 2
    gate_result = await coherence_gate.run(workspace_state)
    if gate_result.passed:
        break
    for route in gate_result.repair_routes:
        await registry.get(route.target_agent).run(route.additional_context)
else:
    if gate_result.escalate_to_user:
        await emit_clarification(gate_result.escalate_to_user)
        return Status.NEEDS_CLARIFICATION
    raise BasefloError(error_code="BF-COHERENCE-001", message="Coherence not reached after repair.")
```

Specialists never loop across each other on their own. Cross-agent repair flows live only here.

---

## 8B. Evidence-Feeding — Deterministic Helper + Reasoning Agent

The single most important pattern for "agentic but not a wrapper" working at scale. Whenever an agent needs to make a semantic judgment based on observable data, the data is **not** dumped at the agent. Instead:

1. **Deterministic Python code computes structural facts.** Counts, overlap rates, existence checks, statistics, normalization. Runs the same way every time. Returns typed Pydantic objects.
2. **The agent receives those typed facts and reasons over them.** The agent's prompt is structured around treating the facts as evidence. The agent decides what the facts *mean* in context.

```
┌────────────────────────┐       typed facts        ┌────────────────────┐
│ Deterministic helper   │ ────────────────────▶    │ Reasoning agent    │
│ (counts, overlaps,     │                          │ (decides meaning   │
│  checks, statistics)   │                          │  in context)       │
└────────────────────────┘                          └────────────────────┘
       no opinions                                        no counting
```

### Where it's used (and required)

- **`EntityReconciler`** — `overlap.py` computes value-overlap rates between candidate join keys across sources. Agent decides whether the rate justifies calling them the same entity, given context.
- **`CoherenceGate`** — `checks.py` enumerates structural inconsistencies (KPI references missing column, cardinality contradictions, etc.). Agent decides BLOCKING vs WARNING, which specialist to re-run.
- **`ColumnClassifier`** — sample values themselves are typed evidence; no separate helper needed because the connector framework already produces typed `SampleColumn.sample_values`. The principle is the same: structured facts in, semantic decision out.
- **Future agents** that ingest observable data must follow this pattern. If a new agent finds itself "scanning rows," that's a signal to extract a deterministic helper.

### Why both halves matter

- **Without the deterministic helper:** the agent does work it's bad at — counting, overlap calculation, exhaustive existence checks. Slow, costly, non-reproducible, easy to fool with weird data shapes.
- **Without the reasoning agent:** you're back to the heuristic anti-pattern (`if overlap > 0.5 then same entity`). Brittle, breaks on edges, exactly what `00-decisions.md` forbids.
- **Together:** the deterministic layer is fast and auditable; the agent layer reasons with full context (semantic types, business meaning, ambiguity policy). Each does what it's best at.

### Rules for evidence-feeding helpers

- **No opinions.** A helper computes; it does not judge. `overlap.py` does not say "they're the same"; it says "0.87 match rate."
- **Typed output.** Helpers return Pydantic models, never `dict[str, Any]`.
- **Pure functions when possible.** Helpers should be deterministic and idempotent; same input → same output.
- **Documented as helpers.** A helper module must be named `<purpose>.py` (`overlap.py`, `checks.py`, `statistics.py`) and live next to the agent it serves.
- **Tested independently.** A helper's unit tests do not involve any agent or LLM call. Golden fixtures only.

### Anti-patterns

- ❌ A helper that returns "yes/no" on a semantic question. (Move the decision to the agent.)
- ❌ An agent that loops over raw rows or recomputes statistics. (Move the computation to a helper.)
- ❌ A helper that uses regex or substring matching for semantic classification. (See `05-coding-rules.md` §1.2.)
- ❌ A helper whose output is a free-form string the agent has to parse. (Return typed structured facts.)

## 9. Saga — Long-Running Multi-Step Flows

Refinements, multi-source re-introspection, and connector-add operations span minutes and multiple steps. We model them as sagas: each step has a forward action and a compensating action.

```python
# app/orchestration/sagas/refine.py
class RefineSaga(Saga):
    steps = [
        Step(forward="interpret_intent",   compensator=None),
        Step(forward="analyze_impact",     compensator=None),
        Step(forward="plan_change",        compensator=None),
        Step(forward="emit_child_ir",      compensator="rollback_child_ir"),
        Step(forward="run_coherence_gate", compensator="discard_child"),
        Step(forward="commit_version",     compensator="hard_delete_child"),
        Step(forward="notify_clients",     compensator=None),
    ]
```

Compensation runs only on terminal failure. On recoverable failure, retry the failed step.

Why sagas instead of database transactions: some steps span LLM calls and external connector calls — operations that cannot be wrapped in a single SQL transaction. Sagas give us the same guarantees at a higher level.

---

## 10. The "Boundary" Rule

Every cross-domain interaction in the system uses one of these patterns:

| Boundary | Pattern |
|---|---|
| External source ↔ engine | Adapter (Connector Protocol) |
| Customer infrastructure ↔ engine | Strategy (DataPlane) |
| LLM provider ↔ agent | Factory + abstraction (Pydantic AI) |
| HTTP request ↔ persisted state | Repository |
| User intent ↔ system state | Command |
| Async event ↔ subscriber | Observer (LISTEN/NOTIFY) |
| Cross-agent repair | Gate |
| Multi-step external workflow | Saga |

If you find yourself building a cross-boundary interaction that doesn't fit one of these patterns, that's a signal to stop and discuss it before introducing a new pattern. New patterns require an entry in this document and sign-off.

---

## 11. The Single Most Important Rule

**Patterns serve the architecture. The architecture serves the product. The product serves the user.** If a pattern in this document gets in the way of any of those, the pattern loses, not the architecture or the product or the user. Update this doc; don't fight the structure.
