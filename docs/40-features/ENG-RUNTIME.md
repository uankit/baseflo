# `ENG-RUNTIME` — Agent Runtime Infrastructure

Status: M0. Combines `ENG-RUNTIME` + `ENG-REGISTRY` + `ENG-ROUTING` + `ENG-REPAIR` + `ENG-CACHE` + `ENG-TRACE` + `ENG-CONC` from [`30-features.md`](../30-features.md). These are tightly coupled into one cohesive subsystem.

---

## 1. Overview

Every agent in the system goes through this runtime. It is responsible for: building Pydantic AI `Agent` instances from `AgentSpec` registrations, routing to model tier, running with output validation and structured repair, caching agent objects and run outputs, recording typed traces, and enforcing per-tenant concurrency limits. Agents themselves are leaves; the runtime is the spine.

This is the module that proved most fragile in the prior audit — sync `asyncio.run` inside async paths, hardcoded model names, dead repair loops, zeroed token usage. The new runtime fixes all of those by design.

## 2. High-Level Design

```
┌──────────────────────────────────────────────────────────────────┐
│                      AgentRuntime                                 │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────┐    │
│  │ Registry     │  │ ModelRouter  │  │ ConcurrencyManager   │    │
│  │ (specs by    │  │ (tier→name)  │  │ (per-tenant limits)  │    │
│  │  name)       │  │              │  │                      │    │
│  └──────┬───────┘  └──────┬───────┘  └──────────┬───────────┘    │
│         │                 │                     │                │
│         └────────┬────────┴─────────────────────┘                │
│                  │                                                │
│                  ▼                                                │
│         ┌──────────────────┐                                      │
│         │ AgentFactory     │  builds + caches pydantic_ai.Agent  │
│         │ (LRU + TTL)      │                                      │
│         └────────┬─────────┘                                      │
│                  │                                                │
│                  ▼                                                │
│         ┌──────────────────┐    ┌──────────────────────────┐     │
│         │ run(input, ctx)  │───▶│ output validator chain   │     │
│         │                  │    │ (raises ModelRetry on    │     │
│         │                  │    │  recoverable issues)     │     │
│         └────────┬─────────┘    └──────────────────────────┘     │
│                  │                                                │
│                  ▼                                                │
│         ┌──────────────────┐                                      │
│         │ TraceRecorder    │  writes agent_runs +                 │
│         │ (post-commit;    │  agent_run_attempts after            │
│         │  separate sess.) │  artifact persistence                │
│         └──────────────────┘                                      │
└──────────────────────────────────────────────────────────────────┘
```

## 3. Low-Level Design

### 3.1 Module Layout

```
server/app/agents/
├── runtime.py                  # AgentRuntime (the orchestrator class)
├── registry.py                 # AgentRegistry, AgentSpec
├── model_routing.py            # AGENT_MODEL_TIERS dict + resolve_model()
├── factory.py                  # _build_agent(): cached pydantic_ai.Agent constructor
├── repair.py                   # repair-loop logic (validator + tier escalation)
├── concurrency.py              # PerTenantSemaphore
├── trace.py                    # TraceRecorder (writes agent_runs / agent_run_attempts)
├── types.py                    # AgentSpec, AgentRunResult, ModelTier, etc.
└── tests/
    ├── test_registry.py
    ├── test_model_routing.py
    ├── test_factory_cache.py
    ├── test_repair_loop.py
    ├── test_concurrency.py
    ├── test_trace.py
    └── test_runtime_integration.py
```

### 3.2 Key Types

```python
class ModelTier(StrEnum):
    FAST       = "fast"
    BALANCED   = "balanced"
    REASONING  = "reasoning"

class AgentSpec(BaseModel, frozen=True):
    name: str
    input_type: type[BaseModel]
    output_type: type[BaseModel]
    instructions: str
    model_tier: ModelTier
    max_repair_attempts: int = 2
    output_validators: list[Callable]
    cache_key_fn: Callable[[BaseModel], str] | None = None

class AgentRunResult(BaseModel, Generic[OutputT]):
    agent_name: str
    output: OutputT
    attempt_count: int
    repair_attempted: bool
    escalated: bool
    model_tier_used: ModelTier
    model_name_used: str
    duration_ms: int
    usage: TokenUsage                      # real, from provider; never zeroed

class TokenUsage(BaseModel):
    input_tokens: int
    output_tokens: int
    cache_read_tokens: int = 0
    cache_write_tokens: int = 0
```

### 3.3 The Runtime Loop

```python
class AgentRuntime:
    async def run(
        self,
        agent_name: str,
        input: BaseModel,
        ctx: RunContext,
    ) -> AgentRunResult:
        spec = AgentRegistry.get(agent_name)
        async with self.concurrency.acquire(ctx.tenant_id):
            for tier in self._tier_escalation_path(spec.model_tier):
                model_name = resolve_model(tier)
                agent = self.factory.build(spec, model_name)
                try:
                    result = await self._run_with_validators(agent, input, ctx, spec)
                    return result.with_tier(tier)
                except OutputValidationExhausted:
                    if tier == ModelTier.REASONING:
                        raise BasefloError(error_code="BF-AGENT-005", ...)
                    continue   # escalate to next tier
```

Tier escalation: a `balanced` agent that exhausts repair attempts is re-run on `reasoning` (one extra attempt). A `reasoning` agent that exhausts repair raises `BF-AGENT-005`. Tracked via `escalated` field.

### 3.4 The Factory & Cache

```python
@lru_cache(maxsize=256)
def _build_agent(
    agent_name: str,
    model_name: str,
    output_schema_hash: str,
    instructions_hash: str,
) -> pydantic_ai.Agent:
    spec = AgentRegistry.get(agent_name)
    return pydantic_ai.Agent(
        model=resolve_provider(model_name),     # OpenAI v1, Anthropic-ready
        output_type=spec.output_type,
        instructions=spec.instructions,
        retries=spec.max_repair_attempts,
    )
```

LRU + TTL (1h). Cache key is configuration, not identity. Re-warms on worker boot.

### 3.5 Trace Recording (Post-Commit)

`TraceRecorder` writes `agent_runs` + `agent_run_attempts` rows on a **separate SQLAlchemy session**, after the artifact has committed. Trace persistence does NOT block `workspace.ready` SSE emission (fixing the prior audit's blocking-trace-write bug).

Real `usage` is captured from `pydantic_ai.RunResult.usage()` and persisted; zeroed counts forbidden.

### 3.6 Concurrency

`PerTenantSemaphore` enforces `BASEFLO_AGENT_MAX_CONCURRENCY` (default 4) per tenant. One tenant cannot starve others. Independent specialists in the data-architect graph (e.g., per-source `ColumnClassifier` runs) execute in parallel up to the limit.

## 4. Design Patterns Applied

| Pattern | Where | Why |
|---|---|---|
| **Factory** | `_build_agent` cached constructor | Heavy `Agent` build cost amortized. |
| **Strategy** | Model tier routing | One agent, multiple model bindings. |
| **Registry** | `AgentRegistry` | Name-keyed spec lookup; centralized conformance. |
| **Decorator** | `@register_agent`, `@trace_agent_run` | Cross-cutting concerns without polluting agent code. |
| **Async Semaphore** | `PerTenantSemaphore` | Industry-standard concurrency control. |

## 5. Test Plan

- Registry tests: register / lookup / duplicate-detection / unknown-name.
- Routing tests: each tier resolves to the configured model name; env-overrides work.
- Factory cache tests: cache hit on identical inputs; miss on changed instructions hash; bounded eviction.
- Repair loop tests: validator-driven retry; tier escalation on exhaustion; terminal `BF-AGENT-005` after reasoning fails.
- Concurrency tests: per-tenant limit enforced; cross-tenant isolation.
- Trace tests: `agent_runs` row written; real token usage; failure on trace insert does not block workspace.ready.
- Integration test: full data-architect graph end-to-end with `TestModel`.
- Coverage: 92%.

## 6. Error Codes

| Code | Condition | Recovery |
|---|---|---|
| `BF-AGENT-001` | Unknown agent name | Boot-time check; deployment fails. |
| `BF-AGENT-002` | Provider auth failed | Surface to operator; user sees neutral error. |
| `BF-AGENT-003` | Output validation failed | Manager-level: `CoherenceGate`-driven repair, or escalation. |
| `BF-AGENT-004` | Concurrency limit reached | 429-style backoff; queued internally. |
| `BF-AGENT-005` | Repair exhausted across tiers | Surface as terminal failure; user sees retry option. |
| `BF-AGENT-006` | Trace persistence failed | Logged; workspace already shipped; ops alert. |

## 7. Dependencies

All agents depend on this. None depend on agents.

## 8. Milestone

- **M0**: full implementation; all 11 Tier 1 agents register and run through this runtime.
- **M1**: integration tests cover the data-architect graph end-to-end.
- **M2**: refinement graph integrates with the same runtime.
- **M3+**: provider abstraction extended for multi-provider routing (Anthropic + OpenAI in one workspace).
