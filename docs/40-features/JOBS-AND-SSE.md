# `JOBS-AND-SSE` — Background Jobs + SSE Pub/Sub

Status: M0. Combines `JOB-QUEUE` + `JOB-RETRY` + `JOB-SCHED` + `SSE-PUBSUB` + `SSE-REPLAY`. The async backbone of the system. Without this, the API thread blocks during generation (audit-flagged regression we are not repeating).

---

## 1. Overview

Two cooperating pieces:

- **Background jobs (`arq` on Redis)**: every long-running operation (generation, refinement, connector sync, export, digest composition) runs in a worker pool, not on the API request thread. Idempotency-keyed; retries with exponential backoff; DLQ for terminal failures.
- **SSE pub/sub via Postgres `LISTEN/NOTIFY`**: events emitted by workers reach the right SSE client in real time across multi-instance deployments without adding Redis pub/sub. Persisted with sequence numbers; clients reconnect and resume from last seen.

Together they ensure: API returns `202 Accepted` instantly; the user sees staged progress live; nothing is lost on a worker restart.

## 2. High-Level Design

```
              POST /api/v1/conversations/messages
                          │
                          ▼
              ┌────────────────────┐
              │  API handler       │  202 Accepted + job_id + sse_url
              └─────────┬──────────┘
                        │ enqueue
                        ▼
              ┌────────────────────┐
              │  arq queue (Redis) │
              └─────────┬──────────┘
                        │
                        ▼
              ┌────────────────────┐
              │  Worker process    │
              │  - runs pipeline   │
              │  - emits events    │
              └─────────┬──────────┘
                        │ INSERT INTO conversation_events
                        │ + NOTIFY conversation_<id>
                        ▼
              ┌────────────────────┐         ┌──────────────────┐
              │  Postgres          │◄────────│  SSE handler     │
              │  (events log)      │ LISTEN  │  (one per client │
              └────────────────────┘         │   connection)    │
                                             └──────────────────┘
                                                      │
                                                      ▼ stream
                                              SSE client (browser)
```

## 3. Low-Level Design

### 3.1 Module Layout

```
server/app/orchestration/jobs/
├── __init__.py
├── arq_settings.py          # arq worker config; Redis URL; concurrency
├── enqueue.py               # API-side: Job model + enqueue helpers
├── tasks/
│   ├── generate.py          # data-architect graph as an arq task
│   ├── refine.py            # refinement graph as an arq task
│   ├── connector_sync.py    # periodic / on-demand source sync
│   ├── export.py            # full data export
│   ├── digest.py            # daily digest composition
│   └── reintrospect.py      # connector schema re-introspection
├── retry.py                 # backoff strategy; max-attempts policy
└── dlq.py                   # failed_jobs writer; ops dashboard hook

server/app/conversation/sse/
├── __init__.py
├── transport.py             # FastAPI SSE response handler
├── pubsub.py                # Postgres LISTEN/NOTIFY wrapper
├── replay.py                # client resume from sequence number
├── events.py                # typed event models
└── tests/
    └── test_sse_replay.py
```

### 3.2 Job Model

```python
class Job(BaseModel):
    id: UUID
    organization_id: UUID
    project_id: UUID | None
    kind: JobKind                              # GENERATE | REFINE | CONNECTOR_SYNC | EXPORT | DIGEST | REINTROSPECT
    payload: dict                              # typed per kind via discriminated union
    idempotency_key: str
    status: JobStatus                          # QUEUED | RUNNING | SUCCEEDED | FAILED | CANCELLED
    attempts: int
    max_attempts: int = 5
    created_at: datetime
    completed_at: datetime | None

class JobBackoff(BaseModel):
    """Exponential with jitter."""
    base_seconds: int = 2
    max_seconds: int = 300
    jitter_pct: float = 0.2
```

Idempotency: same `idempotency_key` returns the existing job rather than creating a new one. Same key + different payload returns `BF-JOB-001`.

### 3.3 SSE Event Model

```python
class EventType(StrEnum):
    CONVERSATION_MESSAGE        = "conversation.message"
    CLARIFICATION_REQUIRED      = "clarification.required"
    AGENT_START                 = "agent.start"
    AGENT_COMPLETE              = "agent.complete"
    VALIDATION_PASSED           = "validation.passed"
    VALIDATION_WARNING          = "validation.warning"
    VALIDATION_FAILED           = "validation.failed"
    ARTIFACT_READY              = "artifact.ready"
    WORKSPACE_READY             = "workspace.ready"
    ERROR_RECOVERABLE           = "error.recoverable"
    ERROR_TERMINAL              = "error.terminal"

class ConversationEvent(BaseModel):
    id: UUID
    conversation_id: UUID
    sequence: int                              # monotonic per conversation
    event_type: EventType
    payload: dict                              # typed per event_type via discriminated union
    created_at: datetime
```

Events are persisted; the channel `conversation_<conversation_id>` carries `NOTIFY` payloads with the new sequence number, prompting subscribers to fetch.

### 3.4 SSE Resume Protocol

Client connects with `Last-Event-ID: <sequence>` header (standard SSE). Server reads `>` that sequence from `conversation_events`, emits any backlog, then enters `LISTEN` mode for new events. Reconnection is transparent.

### 3.5 Scheduled Jobs

`arq` cron entries:
- Daily digest: per-tenant, per-user, at user's local 7am.
- Connector sync: per-connector cadence (5m / 15m / 1h / daily depending on capability).
- Audit log retention: nightly purge based on org retention policy.
- Token rotation reminder: weekly check of soon-expiring connector tokens.

### 3.6 DLQ + Health

Permanent failures (`attempts >= max_attempts`) write to `failed_jobs`. Ops surface in `/admin/health` (internal). Sentry alert on > 10 failures in 1h.

## 4. Design Patterns Applied

| Pattern | Where | Why |
|---|---|---|
| **Producer-Consumer** | API → arq → workers | Standard async architecture. |
| **Pub-Sub** | Postgres `LISTEN/NOTIFY` | Free, multi-instance, one less service to operate. |
| **Idempotency Key** | `Job.idempotency_key` | Safe retries; client deduplication. |
| **Saga (Compensating Action)** | Long-running tasks (generation, refinement) | See [`50-design-patterns.md` §9](../50-design-patterns.md). |
| **Exponential Backoff with Jitter** | `JobBackoff` | Standard distributed-systems hygiene. |

## 5. Test Plan

- Idempotency tests: same key returns same job; different payload raises `BF-JOB-001`.
- Retry tests: simulated transient failure → retry succeeds; permanent failure → DLQ.
- SSE replay tests: client disconnects mid-stream, reconnects with `Last-Event-ID`, receives backlog + new events.
- Multi-instance test (M2+): two worker instances; events emitted by either reach all subscribers (`NOTIFY` is global).
- Scheduled-job tests: time-frozen tests assert digest fires at user's local 7am.
- Coverage: 90%.

## 6. Error Codes

| Code | Condition | Recovery |
|---|---|---|
| `BF-JOB-001` | Idempotency conflict (same key, different payload) | 409 Conflict; client fixes payload. |
| `BF-JOB-002` | Retries exhausted | DLQ; ops alert. |
| `BF-JOB-003` | Job kind not registered | Boot-time fail-fast. |
| `BF-JOB-004` | Job timeout exceeded | Cancel; surface error. |
| `BF-SSE-001` | LISTEN connection failed | Client reconnect with backoff. |
| `BF-SSE-002` | Sequence gap detected on resume | Force full replay; client fetches all. |

## 7. Dependencies

- [`04-database-schema.md`](../04-database-schema.md) — `generation_jobs`, `conversation_events`, `failed_jobs` tables.
- [`05-coding-rules.md`](../05-coding-rules.md) §4 — async/sync correctness rules.
- arq, Redis, Postgres `LISTEN/NOTIFY`.

## 8. Milestone

- **M0**: arq workers running; SSE pub/sub functional; one end-to-end smoke test.
- **M1**: all generation/refinement/sync jobs run through this; SSE replay tested under reconnect scenarios.
- **M2**: scheduled jobs lit (digest, periodic sync); DLQ surface in ops dashboard.
- **M3+**: per-tenant rate limits on job submission; cost-tracking per-tenant per-day.
