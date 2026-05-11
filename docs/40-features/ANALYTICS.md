# `ANALYTICS` — Analytics & Intelligence Layer

Status: M1. Combines `ANA-EVENTS` + `ANA-INGEST` + `ANA-FUNNEL` + `ANA-COHORT` + `ANA-GEO` + `ANA-TOPN` + `ANA-LAPSE` from [`30-features.md`](../30-features.md). The behavioral intelligence on top of the unified schema.

---

## 1. Overview

Once a project's unified schema exists and `KPIPlanner` has produced typed KPI definitions, the analytics layer:
1. Generates a schema-aware event taxonomy.
2. Exposes an event ingestion API (typed; rate-limited).
3. Compiles each KPI to runnable SQL via DuckDB (or the data plane for live queries against customer DB in BYO mode).
4. Renders funnels, cohorts, geographic distributions, top-N tables, and lapsing/at-risk lists in the admin Analytics tab.
5. Detects rolling-window anomalies for the daily digest.

The whole layer is **deterministic** once the agent decided KPI definitions. No LLM calls run on every analytics page load.

## 2. High-Level Design

```
KPIDefinition (from KPIPlanner)              Customer events (from SDK or generated from existing data)
        │                                                    │
        ▼                                                    ▼
┌───────────────────────┐               ┌────────────────────────────┐
│ KPI SQL Compiler      │               │ Event Ingestion API        │
│ (KPIFormula → SQL via │               │ (typed events; batched)    │
│  SQLGlot AST)         │               └────────────┬───────────────┘
└──────────┬────────────┘                            │
           │                                         ▼
           │                                 events table (per project)
           │                                         │
           └────────────┬────────────────────────────┘
                        │
                        ▼
                ┌──────────────────┐
                │ DuckDB / DataPlane│  (HostedCloud: DuckDB on synthetic+events;
                │  Query Executor  │   BYO-DB: live query customer's Postgres)
                └────────┬─────────┘
                         │
                         ▼
                 typed KPI results
                         │
                         ▼
                Admin UI: cards, charts, tables
                Daily digest: top-of-section content
```

## 3. Low-Level Design

### 3.1 Module Layout

```
server/app/engines/analytics/
├── __init__.py
├── event_taxonomy.py           # generate event names from schema (e.g., "order_completed", "booking_created")
├── ingestion.py                # POST /api/v1/events; typed; rate-limited; batched
├── kpi_compiler.py             # KPIFormula -> SQL (SQLGlot AST; per dialect)
├── executors/
│   ├── duckdb.py               # in-process DuckDB for hosted-cloud
│   ├── postgres.py             # remote Postgres for BYO-DB / self-host
│   └── base.py                 # KPIExecutor protocol
├── funnels.py                  # multi-stage event flow analysis
├── cohorts.py                  # week-of-signup retention compute
├── geo.py                      # geographic aggregation when address columns exist
├── top_n.py                    # ranked lists (top customers, products, regions)
├── lapse.py                    # at-risk detection: decay-pattern surfacing
├── anomaly.py                  # rolling-window threshold violations
├── chart_spec.py               # KPI definition -> chart spec for client (deterministic)
└── tests/
    ├── test_event_taxonomy.py
    ├── test_kpi_compiler.py
    ├── test_funnels.py
    ├── test_cohorts.py
    ├── test_lapse.py
    └── fixtures/
```

### 3.2 Event Taxonomy

For a unified schema with `orders` + `order_items` tables (e-commerce-shaped):
- `order_created` — fires when a row is inserted into `orders`.
- `order_completed` — fires when `orders.status` transitions to `completed`.
- `order_refunded` — when `orders.status` transitions to `refunded`.
- `order_item_added` — insert into `order_items`.
- `customer_created` — insert into `customers`.

Generated deterministically from `SchemaIR`:
- Every reconciled entity gets a `<entity>_created` event.
- Every `STATUS` column with enum transitions gets `<entity>_<transition>` events.
- Every relationship's many-side gets a `<from_entity>_<to_entity>_added` event.

### 3.3 Event Ingestion

```python
# POST /api/v1/projects/:id/events
class EventIngestionRequest(BaseModel):
    events: list[Event] = Field(max_length=500)      # batch limit

class Event(BaseModel):
    name: str                                        # must be in the project's taxonomy
    occurred_at: datetime
    actor_id: str | None = None                      # customer/user id
    properties: dict[str, str | int | float | bool] = {}
    idempotency_key: str | None = None
```

Ingested events:
1. Validated against the taxonomy (unknown event name → `BF-ANA-001`).
2. Written to `events` table (per-project, partitioned by month).
3. Available to KPI execution and funnel computation immediately.

### 3.4 KPI Compilation

`KPIFormula` (typed tree from `KPIPlanner`) → SQLGlot AST → dialect-specific SQL string.

```python
# Example: KPI "Revenue this week"
KPIDefinition(
    name="Revenue this week",
    kind=TIME_SERIES,
    grain=KPIGrain(table="orders", deduplication_columns=["id"]),
    formula=KPIFormula(
        op=KPIOp.SUM,
        column=ColumnRef(table="orders", column="amount_minor"),
    ),
    time_dimension=ColumnRef(table="orders", column="completed_at"),
    filters=[KPIFilter(column=ColumnRef(table="orders", column="status"), op=FilterOp.EQ, value="completed")],
)
# Compiles to (Postgres):
# SELECT date_trunc('week', completed_at) AS bucket,
#        SUM(amount_minor) / 100.0 AS value
# FROM orders
# WHERE status = 'completed'
#   AND completed_at >= now() - interval '7 days'
# GROUP BY bucket
# ORDER BY bucket;
```

The compiler emits **typed SQL** via SQLGlot (no string concatenation). Money columns auto-divide by minor unit (100 for USD cents, etc.) when rendering.

### 3.5 Funnels

Multi-stage event flow. Example for e-commerce: `customer_created → order_created → order_completed → repeat_order`.

```python
class FunnelDefinition(BaseModel):
    stages: list[FunnelStage]                        # ordered
    cohort_window: timedelta = timedelta(days=30)    # how long users have to progress

class FunnelStage(BaseModel):
    event_name: str
    filters: list[KPIFilter] = []
```

Computed by walking events per `actor_id` in time order, counting stage progressions.

### 3.6 Cohort Retention

Bucket users by `created_at` week. For each cohort, compute the fraction still active (had a meaningful event) at week 1, 2, 4, 8, 12. Output is a triangular matrix rendered as a heatmap.

### 3.7 Lapsing / At-Risk

For each "active-frequency entity" (customer with regular activity), compute the gap from last activity to now. Customers whose gap exceeds 2× their personal average → lapsing. Customers with no activity in 60 days who used to be regular → at-risk. Surfaced as a list in admin + the daily digest.

### 3.8 Anomaly Detection

Rolling-window threshold violations on key metrics. For each KPI of kind COUNTER or TIME_SERIES, compute 7-day rolling average; flag values >2σ from the mean. Surface in daily digest as *"Yesterday's failed payments: 14, vs. 3-day average of 4. Worth a look."*

Pure deterministic (no LLM); the output is a typed `Anomaly` record consumed by the digest composer.

### 3.9 Chart Spec Emission

Per-KPI deterministic mapping to chart shape:
- `COUNTER` → number card with delta vs prior period.
- `TIME_SERIES` → line chart.
- `DISTRIBUTION` → histogram.
- `COMPARISON` → bar chart.
- `FUNNEL` → funnel diagram.
- `COHORT` → heatmap.
- `TOP_N` → ranked table.

## 4. Design Patterns Applied

| Pattern | Where | Why |
|---|---|---|
| **Strategy** | `KPIExecutor` protocol; DuckDB and Postgres implementations | Same KPI definition, different execution backend. |
| **Visitor** | KPI formula → SQL AST traversal | Typed tree maps cleanly to SQLGlot expressions. |
| **Composite** | `KPIFormula` recursive structure | Nested SUMs, RATIOs, conditions. |
| **Pipeline** | Events → ingestion → storage → KPI execution → chart | Each step pure where possible. |

## 5. Test Plan

- Event taxonomy: deterministic generation from fixtures.
- KPI compiler: every formula shape compiles to expected SQL; round-trip via SQLGlot parse.
- KPI execution: against real DuckDB with seeded fixture data; numbers match expected.
- Funnel: synthetic event stream → expected stage counts.
- Cohort: weekly cohorts → expected retention matrix.
- Lapse: synthetic activity → expected lapsing list.
- Anomaly: synthetic time series with injected spike → flagged correctly.
- Coverage: 90%.

## 6. Error Codes

| Code | Condition | Recovery |
|---|---|---|
| `BF-ANA-001` | Unknown event name (not in taxonomy) | 400; SDK shows suggestion. |
| `BF-ANA-002` | Event ingestion rate-limited | 429 with Retry-After. |
| `BF-ANA-003` | KPI execution failed (SQL error) | Surface to operator; UI shows "metric temporarily unavailable." |
| `BF-ANA-004` | KPI execution timeout | Surface; configurable per-KPI timeout. |
| `BF-ANA-005` | Funnel definition references unknown event | 400 at definition time, not runtime. |

## 7. Dependencies

[`AGENT-KPI`](AGENT-KPI.md), [`IR-CORE`](IR-CORE.md), [`SECURITY`](SECURITY.md) (PII fields excluded from analytics by default), DuckDB, SQLGlot.

## 8. Milestone

- **M1**: event taxonomy + ingestion + KPI compiler + chart spec; analytics tab functional for the friend's case.
- **M2**: funnels + cohorts + lapsing list + multi-source aware analytics (events from connector data and from SDK both contribute).
- **M3**: anomaly detection + daily-digest integration.
- **M4+**: custom funnels in UI; saved metric views; exports.
