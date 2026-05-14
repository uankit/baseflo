# Baseflo Adaptive Operating Intelligence

Baseflo is the adaptive operating intelligence layer for a business.

It connects to the places where a business already lives, learns the shape of the
data without templates, watches for meaningful change, explains why it matters,
and proposes controlled next moves.

## Product Stance

Baseflo is not:

- a spreadsheet copilot;
- a dashboard builder;
- a generic agent builder;
- a vertical template catalog;
- AI employee cosplay.

Baseflo is the business state layer that serious agents need before they can
act. It earns trust by first understanding and explaining the business, then
moving into governed action.

## Continuous Loop

1. Sense: ingest and profile connected sources.
2. Model: infer assets, columns, relationships, metrics, events, and memory.
3. Watch: detect change, drift, anomalies, bottlenecks, and opportunities.
4. Explain: produce grounded narratives with lineage and confidence.
5. Act: propose safe next steps across tools.
6. Learn: remember approvals, dismissals, definitions, and business context.

## Product Surfaces

- Brief: the daily operating update.
- Map: sources, assets, columns, relationships, and memory.
- Metrics: tracked values with definitions, history, and lineage.
- Watchtower: anomalies, risks, opportunities, and data-quality changes.
- Actions: proposed tasks, updates, alerts, and write-backs awaiting approval.

## Engineering Boundary

LLMs own semantic judgment and synthesis. Deterministic systems own profiling,
SQL execution, metric computation, anomaly detection, permissions, encryption,
idempotency, audit, and rollback.

No user-facing business templates are allowed in the core path. Any metric or
insight must be supported by observed data and carried with evidence.
