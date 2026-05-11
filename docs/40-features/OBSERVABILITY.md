# `OBSERVABILITY` — Logs, Traces, Metrics, Errors, Status

Status: M0–M1. Combines `OPS-LOGS` + `OPS-TRACES` + `OPS-METRICS` + `OPS-SENTRY` + `OPS-STATUS`. The visibility layer; without this, debugging production is guesswork.

---

## 1. Overview

Five primitives together:

1. **Structured logs** (`structlog`) — JSON, per-tenant context, PII-scrubbed.
2. **Distributed traces** (OpenTelemetry) — every API request, agent run, connector call, DB query.
3. **Metrics** (Prometheus-format) — latency, queue depth, repair rates, token usage, per-tenant cost.
4. **Error tracking** (Sentry) — unhandled exceptions; release-tagged; per-tenant tagged.
5. **Status page** (`status.baseflo.com`) — real-time uptime + incident comms.

Cost dashboard (M2+) rolls up token usage per tenant per day → input to billing checks and per-customer profitability.

## 2. High-Level Design

```
                   structlog ──▶ JSON to stdout ──▶ Loki/Datadog
Engine workers     OpenTelemetry SDK ─▶ OTLP exporter ─▶ Honeycomb
                   prometheus_client ──▶ /metrics endpoint ──▶ Prometheus scrape
                   Sentry SDK ──▶ Sentry.io
                                                                    │
                                                                    ▼
                                                          Grafana dashboards (in repo: infra/grafana/)
                                                          PagerDuty on critical alerts
                                                                    │
                                                                    ▼
                                                            status.baseflo.com (StatusPage.io or self-hosted)
```

## 3. Low-Level Design

### 3.1 Module Layout

```
server/app/observability/
├── __init__.py
├── logging.py              # structlog config + PII scrubber processor
├── tracing.py              # OpenTelemetry init; FastAPI/SQLAlchemy/aiohttp instrumentation
├── metrics.py              # Prometheus counters/histograms for our domain
├── sentry.py               # Sentry init + tagging
├── context.py              # ContextVars: tenant_id, request_id, job_id, agent_run_id
└── tests/

infra/
├── grafana/                # dashboards as code
├── prometheus/             # scrape config
└── alertmanager/           # alert routing rules
```

### 3.2 Logging

`structlog` JSON output. Every log line includes:

```json
{
  "ts": "2026-05-06T14:23:01.234Z",
  "level": "info",
  "msg": "agent run completed",
  "tenant_id": "org_01HZX...",
  "request_id": "req_01HZX...",
  "job_id": "job_01HZX...",
  "agent_name": "EntityReconciler",
  "duration_ms": 4321,
  "input_tokens": 1234,
  "output_tokens": 567
}
```

Context vars (`tenant_id`, `request_id`, `job_id`, `agent_run_id`) are set by middleware/decorators and propagated automatically. No `print()` outside CLI.

PII scrubber processor: any field whose path matches a known PII column for the active tenant gets redacted. The known-PII map is computed once per `project_versions` row and cached.

### 3.3 Tracing

OpenTelemetry SDK initialized per worker. Auto-instrumentation for:
- FastAPI requests (one root span per HTTP call).
- SQLAlchemy queries (child spans).
- aiohttp (connector outbound calls).
- Pydantic AI runs (custom instrumentation: one span per agent run with input/output hashes as attributes; never raw payloads).

Sampling: 100% of error paths; 10% of healthy-path traces in production; 100% in staging. Per-tenant override available for debugging.

OTLP exporter pushes to Honeycomb (our preference) or whichever backend the operator configures.

### 3.4 Metrics

Domain metrics (in addition to standard FastAPI / SQLAlchemy / arq metrics):

```python
agent_runs_total = Counter(
    'baseflo_agent_runs_total', 'Agent runs',
    labels=['agent_name', 'tier', 'final_status']
)
agent_run_duration_ms = Histogram(...)
agent_repair_attempts = Counter(...)
agent_token_usage = Counter(..., labels=['agent_name', 'kind'])  # kind=input|output|cache_read|cache_write
coherence_gate_repair_cycles = Histogram(...)
job_queue_depth = Gauge(..., labels=['kind'])
job_duration_ms = Histogram(..., labels=['kind', 'final_status'])
connector_call_duration_ms = Histogram(..., labels=['connector_name', 'method'])
connector_failures_total = Counter(..., labels=['connector_name', 'error_code'])
sse_active_connections = Gauge(...)
sse_events_emitted_total = Counter(..., labels=['event_type'])
api_requests_total = Counter(..., labels=['route', 'status_code'])
api_request_duration_ms = Histogram(..., labels=['route'])
```

Per-tenant cost roll-up (M2+): `agent_token_usage` grouped by `tenant_id` + day → cost computed from provider rate card → input to per-customer profitability dashboard and to alerting on outlier tenants (a tenant burning $X/day is investigated).

### 3.5 Sentry

Unhandled exceptions auto-captured. Release tag from git SHA. Per-tenant tag (`organization_id`) for filtering. Breadcrumbs include the last 50 log entries of the request. Sensitive data scrubbed via the same PII scrubber processor as logs.

### 3.6 Status Page

`status.baseflo.com` — components:
- API
- Hosted-Cloud Postgres
- Hosted-Cloud Redis
- LLM Provider (OpenAI / Anthropic) — surfaced separately so customers see when an upstream issue affects us
- SSE
- Connectors (per built-in connector)
- Daily Digest delivery

Component status auto-updated from health-check probes; incidents posted by ops within 5 minutes of detection. Post-mortems published within 5 business days of P1.

### 3.7 Alerts

PagerDuty rules:
- API error rate > 1% over 5 min → P2 page.
- Agent failure rate (after repair) > 5% over 15 min → P3.
- Job queue depth > 1000 sustained → P3.
- Hosted-Cloud Postgres CPU > 85% sustained → P2.
- Customer DB (BYO-DB) unreachable for any tenant > 5 min → P3 (notify customer + ops).
- LLM provider 5xx rate > 10% over 5 min → P3 (status page only; no user-impact action available).

## 4. Design Patterns Applied

| Pattern | Where | Why |
|---|---|---|
| **Decorator** | `@trace_agent_run`, structlog processors | Cross-cutting; never leaks into business code. |
| **Context Variables** | `tenant_id` / `request_id` propagation | Async-safe context across the whole request. |
| **Adapter** | OTLP exporter; Sentry SDK | Vendor-flexible. |
| **Singleton** | OpenTelemetry tracer; structlog logger | One per process, lazy-initialized. |

## 5. Test Plan

- Logging: every log line has tenant_id/request_id when applicable.
- PII scrub: log records with PII column values are redacted.
- Tracing: agent run spans correctly nested under request span; input/output hashes only (no raw text).
- Metrics: cardinality bounded (agent_name × tier × status is tractable).
- Sentry: scrubbing applied to breadcrumbs and exception payloads.
- Status: component health probes + manual incident lifecycle.
- Coverage: 88%.

## 6. Error Codes

| Code | Condition | Recovery |
|---|---|---|
| `BF-OBS-001` | Telemetry export failure | Logged but never blocks request. |
| `BF-OBS-002` | Sampling decision error | Default to 100% sample rate; alert. |

## 7. Dependencies

structlog, OpenTelemetry SDK + auto-instrumentation libs, prometheus_client, Sentry Python SDK, [`AUTH`](AUTH.md) (TenantCtx supplies tenant_id), [`SECURITY`](SECURITY.md) (PII scrub list).

## 8. Milestone

- **M0**: structlog + OpenTelemetry init; basic metrics; Sentry; manual status page.
- **M1**: full domain metrics + Grafana dashboards committed; per-route latency SLOs.
- **M2**: per-tenant cost dashboard; alerts wired to PagerDuty.
- **M3**: status page automation + per-tenant uptime reports for enterprise customers.
