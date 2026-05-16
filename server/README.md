# Baseflo Server

Baseflo turns connected business data into a canonical data plane, profiles it, lets single-responsibility agents plan useful investigations, executes those plans deterministically, records business memory, and returns operating artifacts for Brief, Inbox, and Ask.

## Architecture

```text
┌─────────────────────────────────────────────────────────────┐
│                         Frontend                            │
│  Brief newspaper │ Inbox actions │ Ask canvas │ Sources     │
└────────────────────────┬────────────────────────────────────┘
                         │ REST commands + SSE run events
┌────────────────────────▼────────────────────────────────────┐
│                         API Layer                           │
│  Auth │ Connections │ Source Sync │ Operating Run           │
└────────────────────────┬────────────────────────────────────┘
                         │
┌────────────────────────▼────────────────────────────────────┐
│                    Operating Pipeline                       │
│  refresh data plane → profile → plan → execute → narrate    │
└────────────────────────┬────────────────────────────────────┘
                         │
┌────────────────────────▼────────────────────────────────────┐
│                         Planes                              │
│  Connector Runtime  │ Data Plane       │ Data Profiler      │
│  Agent Plane        │ Execution Plane  │ Memory Plane       │
│  Business View      │ Artifact Plane   │ Action Plane       │
│  Communication                                              │
└─────────────────────────────────────────────────────────────┘
```

## Principles

1. **Source adapters only fetch.** Connectors return source-shaped records and metadata; they do not interpret business meaning.
2. **The data plane canonicalizes first.** Any source is normalized into canonical assets, fields, records, and graph edges before intelligence starts.
3. **The profiler is deterministic.** It produces type profiles, quality signals, key candidates, relationship candidates, freshness, and compact evidence packs.
4. **Agents only plan and explain.** They receive canonical context and emit typed contracts. They do not invent table or column names, execute SQL, or mutate sources directly.
5. **Execution is deterministic.** The execution plane validates typed analysis plans, compiles them with safe identifiers, runs them against canonical data, and returns evidence.
6. **Memory is business memory.** Durable facts, preferences, validated meanings, and dismissed/accepted learnings are stored independently from chat/session memory.
7. **Persistence is behind stores.** Plane services use typed records/contracts. SQLAlchemy models and sessions stay inside package `store.py` modules or the `db/` infrastructure.

## Packages

| Package | Purpose |
|---------|---------|
| `auth/` | Auth token helpers, auth-domain workflows, membership checks, and auth persistence boundary |
| `connector_runtime/` | Connector execution boundary and source adapter orchestration |
| `data_plane/` | Canonicalization, graph construction, sheet extraction, and canonical contracts |
| `data_profiler/` | Deterministic profiling for fields, assets, quality, keys, relationships, and freshness |
| `agent_plane/` | Agent contracts, context packs, factories, prompts, and operating plans |
| `execution_plane/` | Plan normalization, validation, SQL compilation, execution, and result contracts |
| `memory_plane/` | Autonomous business memory contracts and persistence |
| `business_view_plane/` | Generated operating-room sections, entity views, and Ask drill-down prompts |
| `artifact_plane/` | Durable Brief, Inbox, Ask, evidence, lineage, and action artifact read model |
| `action_plane/` | Internal action records for email drafts, export lists, and saved cohorts |
| `operating_pipeline/` | End-to-end orchestration for `scan` and `ask` operating runs |
| `communication/` | Baseflo run lifecycle contracts, event bus, and SSE response helpers |
| `api/` | FastAPI routes for auth, connectors, data, OAuth, operating runs, artifacts, and actions |

## Communication Standard

- **REST + JSON** is the command/read surface: create connectors, request source syncs, start runs, fetch run state, fetch completed artifacts.
- **SSE + JSON event envelopes** is the live progress surface for long-running work: source sync, operating runs, exports, and action execution.
- **Schedulers/jobs** should create the same run records and publish the same events as user-triggered runs.
- **WebSockets** are reserved for later collaborative editing or bidirectional live workspaces.
- **Protobuf is not used in v1.** Typed Pydantic/TypeScript JSON contracts are the source of truth until payload size or cross-language pressure makes binary contracts worth it.

Standard async flow:

```text
POST /api/v1/<domain>/runs  -> 202 RunAccepted { run_id, result_url, events_url }
GET  /api/v1/<domain>/runs/{run_id} -> RunState { run, events[] }
GET  /api/v1/<domain>/runs/{run_id}/events -> text/event-stream RunEvent
GET  /api/v1/<domain>/runs/{run_id}/result -> typed domain result
```

## Development

```bash
uv sync
uv run alembic upgrade head
uv run uvicorn app.main:app --reload
```
