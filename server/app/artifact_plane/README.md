# Artifact Plane

Artifact Plane is the durable product read model for Baseflo intelligence.

It receives an `OperatingRunResult` and creates stable artifacts for:

- Brief
- Inbox
- Ask answers
- Insights
- Charts
- Tables
- Audiences
- Lineage
- Proposed actions

The package is deterministic. It does not call agents, execute queries, or know
frontend components. Its job is to turn structured run output into lifecycle
objects with `title`, `summary`, `why`, `tags`, `source_refs`, and `payload`.

Artifact lifecycle belongs here for now: `new`, `seen`, `snoozed`, `dismissed`,
and `resolved`. Future Action Plane can own action execution while referencing
the action artifacts created here.
