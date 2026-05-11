# Baseflo Alpha Intelligence Architecture

Status: alpha implementation spine. The initial build path now runs through
`WorkspaceBuildGraph` with a graph-owned execution engine, while preserving the
existing specialist agents and typed IR contracts.

## Thesis

Baseflo is not a data migration product and not an LLM wrapper. For alpha, the
valuable wedge is:

1. A founder connects messy operational sources such as Google Sheets, Excel,
   CSV, Shopify, Stripe, and Postgres.
2. Baseflo profiles the data without sending bulk raw rows to a model.
3. Specialist agents reconcile the founder's business into one canonical model.
4. Deterministic compilers build a workspace: admin views, metrics, dashboards,
   segments, reports, and daily operating notes.
5. User corrections become durable feedback, reducing manual work over time.

The product promise is "decision-ready operating data in under five minutes,"
not "move your data into our warehouse."

## Architecture Decision

Use both Pydantic Graph and Postgres:

- **Pydantic Graph** is the build-time control plane. It owns typed state,
  node transitions, bounded repair cycles, pause/resume, and human-in-loop
  clarification.
- **Postgres** is the durable intelligence plane. It stores source snapshots,
  profile evidence, agent artifacts, canonical IDs, build traces, feedback
  events, and versioned workspace artifacts.
- **Pydantic AI agents** remain typed specialist workers. They run inside graph
  nodes and emit typed artifacts only.
- **Deterministic engines** profile, validate, compile, execute, and write.
  Agents never emit SQL and never receive unbounded raw datasets.

## Data Flow

```text
Connector read/sync
  -> SourceSnapshot
  -> DeterministicProfiler
  -> SourceEvidenceBundle
  -> WorkspaceBuildGraph
      -> BusinessContextAgent
      -> ColumnClassifier
      -> EntityReconciler
      -> CardinalityResolver
      -> ConstraintProposer
      -> PhysicalSchemaArchitect
      -> KPIPlanner
      -> InsightAnalyst
      -> SegmentPlanner
      -> ReportPlanner
      -> CoherenceGate
          -> repair routes or clarification
  -> CanonicalStore + ArtifactStore
  -> Admin UI + Analytics + Digest + Reports + Action Queue
```

## Privacy And Scale

For thousands or millions of rows, the LLM sees:

- schema metadata,
- bounded examples,
- deterministic profiles,
- overlap statistics,
- sampled anomalies,
- top values and distributions,
- evidence hashes and provenance.

The LLM does not see whole tables. For sensitive deployments, raw rows stay in
the customer's source or BYO database; Baseflo stores only connector metadata,
profile evidence, canonical IDs, and derived artifacts unless hosted canonical
storage is explicitly enabled.

## New Durable Concepts

- `source_snapshots`: one versioned introspection/sample bundle per connector
  sync.
- `source_evidence`: deterministic profiles keyed by snapshot.
- `workspace_builds`: graph run state, current phase, repair cycle, status.
- `workspace_artifacts`: typed agent outputs, content hashes, provenance.
- `entity_resolution_edges`: source row/entity identity links with confidence,
  evidence, and user overrides.
- `metric_catalog`: KPI definitions plus compiled query metadata.
- `insight_packs`: generated observations, segments, and recommended actions.
- `feedback_events`: user corrections, hidden KPIs, merged/split entities,
  metric edits, and report edits.

## Alpha Graph

The first production graph should be:

1. `LoadSources`: load active connectors and latest snapshots.
2. `ProfileSources`: compute deterministic evidence bundles.
3. `ClarifyBusiness`: ask at most three blocking questions only if source
   evidence plus description is insufficient.
4. `ClassifyColumns`: per source, parallel.
5. `ReconcileEntities`: multi-source identity and authority decisions.
6. `ResolveRelationships`: cardinalities and join paths.
7. `ProposeConstraints`: keys, money, statuses, nullability, PII rules.
8. `ComposeSchema`: canonical `SchemaIR`.
9. `PlanMetrics`: answerable KPIs and skipped KPIs.
10. `PlanInsightSurfaces`: dashboard, segments, digest, report outline.
11. `CoherenceGate`: deterministic findings plus agent review.
12. `ApplyRepairRoutes`: re-run targeted nodes up to two cycles.
13. `CommitWorkspace`: persist version, apply DDL, backfill/virtualize data,
    emit `workspace.ready`.

## Alpha Wow Factor

For a Sheets-heavy founder, the first five-minute win should be:

- "We found 6 sheets and reconciled Customers, Orders, Leads, Products."
- "These three sheets appear to be the same customer list; email is the stable
  identity. Sheets is authoritative for phone, Shopify for order history."
- "Here are the top revenue products, repeat customers, abandoned leads, and
  regions with the most activity."
- "Here are 20 customers worth reaching out to today, with the reason for each."
- "Here is a presentation/report you can send to your team."

That is the buyable value. The admin UI is useful, but the operating insights
are the emotional hook.

## Migration Plan

1. Align typed contracts so validators never contradict prompts or IR rules.
2. Introduce deterministic source evidence profiling and pass it to agents.
3. Persist build state and agent artifacts.
4. Replace the legacy one-pass initial build flow with a Pydantic Graph manager.
5. Implement CoherenceGate repair-route application, not terminal failure.
6. Add row-level entity resolution and canonical ID merging.
7. Wire KPI execution and analytics endpoint to real canonical data.
8. Add `InsightAnalyst`, `SegmentPlanner`, and `ReportPlanner` after the schema
   and KPI path is stable.
