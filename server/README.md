# Baseflo Brain v2

Autonomous business intelligence. Your data stays where it is. Baseflo thinks about it for you.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                        Frontend                             │
│  Insight Feed  │  Drill-down Chat  │  Source Manager       │
└────────────────────────┬────────────────────────────────────┘
                         │ WebSocket + REST
┌────────────────────────▼────────────────────────────────────┐
│                        API Layer                            │
│  Auth │ Projects │ Connectors │ Insights │ KPIs │ Query    │
└────────────────────────┬────────────────────────────────────┘
                         │
┌────────────────────────▼────────────────────────────────────┐
│                      Brain Layer                            │
│  DiscoveryAgent → RelationshipAgent → AnalystAgent         │
│         ↓                ↓                    ↓            │
│  Semantic Layer → Insight Engine → KPI Tracker            │
└────────────────────────┬────────────────────────────────────┘
                         │
┌────────────────────────▼────────────────────────────────────┐
│                      Sync Layer                             │
│  Connector Protocol → Sync Engine → Raw Data Store (PG)    │
└─────────────────────────────────────────────────────────────┘
```

## Core Principles

1. **Agents propose, engineering executes.** LLMs generate hypotheses, configs, and narratives. Deterministic code validates, executes, and stores.
2. **Data never moves to us.** Sources sync to the user's own Postgres (tenant-isolated). We store metadata, insights, and query logic — not their raw business data.
3. **The brain is proactive.** It watches data, detects patterns, and surfaces insights without being asked.
4. **Every insight is traceable.** SQL, confidence scores, and raw data pointers are attached to every insight.

## Modules

| Module | Purpose |
|--------|---------|
| `connect/` | Pluggable source connectors (Sheets, Stripe, Postgres, etc.) |
| `sync/` | Pulls data from sources into tenant-isolated Postgres tables |
| `semantic/` | Auto-discovers schema, labels columns, detects relationships |
| `insight/` | Statistical engine: anomalies, trends, correlations, segments |
| `brain/` | LLM orchestration: narratives, query generation, recommendations |
| `query/` | Natural language → SQL execution with result narrative |
| `api/` | FastAPI routes |
| `ws/` | WebSocket for real-time insight push |

## Development

```bash
uv sync
uv run alembic upgrade head
uv run uvicorn app.main:app --reload
```
