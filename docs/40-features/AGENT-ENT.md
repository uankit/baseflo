# `AGENT-ENT` — EntityReconciler (THE MOAT)

Status: M1 (single-source path) → M2 (full multi-source path). The single most differentiated agent in the system.

---

## 1. Overview

`EntityReconciler` is the agent that decides which logical entities span which sources. It looks at multiple `ColumnClassifier` outputs (one per source) and answers: *"Which of these source tables represent the same business concept (Customer, Order, Product, etc.)? When they do, how do rows correspond? When fields conflict, who's authoritative? When merging, what strategy?"*

This is the moat. Airbyte/Fivetran ingest data and dump it into a warehouse. HubSpot/Zoho make customers migrate to them. Nobody — until us — *agentically reconciles* a customer's existing tools into one coherent business view. Get this agent right and Baseflo is irreplaceable. Get it wrong and we're another integration layer.

It does NOT design the physical schema (`PhysicalSchemaArchitect`), does NOT decide cardinality (`CardinalityResolver`), does NOT propose constraints (`ConstraintProposer`). It produces an `EntityReconciliationPlan` that downstream agents and compilers consume.

## 2. High-Level Design

```
┌──────────────────────────────────────────────┐
│ ColumnClassifier outputs (one per source)    │
│  + connector metadata + sample-row overlap   │
└─────────────────┬────────────────────────────┘
                  │
                  ▼
        ┌──────────────────────────┐
        │  EntityReconciler        │
        │  (model_tier: reasoning) │
        └────────────┬─────────────┘
                     │
                     ▼
        ┌──────────────────────────────────────┐
        │ EntityReconciliationPlan             │
        │   reconciled_entities[*]:            │
        │     canonical_name                   │
        │     contributing_sources[*]:         │
        │       connector + table              │
        │       column_mapping (canonical→src) │
        │     join_keys                        │
        │     conflict_policy:                 │
        │       authoritative_source_per_field │
        │     merge_strategy                   │
        │     ambiguities[*] (typed)           │
        └────────────┬─────────────────────────┘
                     │
                     ▼
        feeds: CardinalityResolver, ConstraintProposer,
               PhysicalSchemaArchitect, KPIPlanner
```

## 3. Low-Level Design

### 3.1 Module Layout

```
server/app/agents/specialists/entity_reconciler/
├── __init__.py
├── agent.py
├── prompt.py
├── types.py
├── overlap.py            # Deterministic helper: pre-computes row-value overlap stats by candidate join keys
└── tests/
    ├── test_validator.py
    ├── test_with_test_model.py
    └── fixtures/
        ├── single_source_only.json
        ├── shopify_plus_excel_customers.json
        ├── stripe_plus_mailchimp_plus_notion.json
        └── conflicting_authoritative.json
```

### 3.2 Key Types

```python
# types.py
class EntityReconcilerInput(BaseModel):
    classified_sources: list[ClassifiedSource]   # one per connector
    overlap_stats: list[OverlapStat]             # deterministic pre-computed signals (see §3.4)

class ClassifiedSource(BaseModel):
    connector_name: str
    source_name: str
    classified_columns: list[ClassifiedColumn]   # from ColumnClassifier

class OverlapStat(BaseModel):
    """Pre-computed value-overlap signals between candidate join keys
    across two sources. Deterministic; informs the agent but does not
    decide for it."""
    source_a: SourceRef
    source_b: SourceRef
    candidate_key_a: str                         # canonical name
    candidate_key_b: str
    sample_match_rate: Annotated[float, Field(ge=0.0, le=1.0)]
    sample_size: int

class ColumnMapping(BaseModel):
    canonical_name: str                          # the name in the reconciled entity
    contributions: list[SourceColumnContribution]  # which source's columns feed this canonical column

class SourceColumnContribution(BaseModel):
    connector_name: str
    source_table: str
    source_column: str
    confidence: Annotated[float, Field(ge=0.0, le=1.0)]

class JoinKey(BaseModel):
    source_a: SourceRef
    source_b: SourceRef
    columns_a: list[str]                         # canonical names on side A
    columns_b: list[str]                         # canonical names on side B
    transformation: JoinTransform = JoinTransform.LOWERCASE_TRIM   # enum

class ConflictPolicy(BaseModel):
    """Per canonical column: which source wins when fields disagree."""
    authoritative_source: dict[str, str]         # canonical_column_name -> connector_name
    rationale: dict[str, str]                    # canonical_column_name -> short explanation

class MergeStrategy(StrEnum):
    PREFERRED_SOURCE      = "preferred_source"      # take fields from the authoritative source
    LATEST_WRITE_WINS     = "latest_write_wins"     # use most recent updated_at across sources
    UNION                 = "union"                 # combine all fields; flag duplicates as warnings
    AGGREGATE             = "aggregate"             # sum/avg specific fields (rare; explicit list)

class ReconciledEntity(BaseModel):
    canonical_name: str = Field(pattern=r"^[A-Z][a-zA-Z0-9]*$")  # e.g., "Customer", "Order"
    canonical_table_name: str = Field(pattern=r"^[a-z][a-z0-9_]*$")  # snake_case for DB
    label: str                                   # plural user-facing ("Customers")
    contributing_sources: list[ContributingSource]
    column_mappings: list[ColumnMapping]
    join_keys: list[JoinKey]
    conflict_policy: ConflictPolicy
    merge_strategy: MergeStrategy
    primary_key_strategy: PrimaryKeyStrategy     # GENERATED_UUID | COMPOSITE_FROM_SOURCES | INHERIT_AUTHORITATIVE

class ContributingSource(BaseModel):
    connector_name: str
    source_table: str
    role: SourceRole                             # AUTHORITATIVE_PRIMARY | AUGMENTING | LOG_ONLY

class Ambiguity(BaseModel):
    """When the reconciler is unsure between two interpretations.
    The manager decides whether to surface as a clarification or accept with assumption."""
    target: str                                  # "entity:Customer" | "join_key:Stripe.email↔Notion.Email"
    description: str                             # plain-English description for ClarificationAgent if escalated
    options: list[AmbiguityOption]
    recommended: int                             # index into options
    recommendation_confidence: Annotated[float, Field(ge=0.0, le=1.0)]

class EntityReconciliationPlan(BaseModel):
    reconciled_entities: list[ReconciledEntity]
    unreconciled_tables: list[UnreconciledTable]  # tables not part of any reconciled entity (kept as-is)
    ambiguities: list[Ambiguity]
    assumptions: list[Assumption]                # explicit assumptions surfaced for the workspace
```

### 3.3 The Prompt (in `prompt.py`)

≥350 words (this is a reasoning-tier agent; the prompt is meatier than `ColumnClassifier`).

Required sections:

1. **Persona**: *"You are Baseflo's entity reconciler. You decide which source tables represent the same business concept (a Customer in Stripe is the same person as a contact in Mailchimp), how rows from different sources correspond, and which source is authoritative for each field when they disagree."*

2. **Job**: detailed paragraph describing reconciliation as the agent's product, with explicit framing that this is the moat.

3. **Inputs**: typed shape (`EntityReconcilerInput`) with explanation of what `OverlapStat` means and how to use it as evidence.

4. **Output schema**: full `EntityReconciliationPlan` signature embedded.

5. **Reasoning rules** (8-10 bullets):
   - *Two source tables represent the same entity if and only if they have a join key with sample match rate ≥ 0.5 AND their column semantic types overlap meaningfully.*
   - *Use `OverlapStat` as evidence; never invent join keys without overlap support.*
   - *Authoritative-source decisions consider: connector authoritativeness for the field's semantic domain (Stripe is authoritative for billing; Notion for notes; Sheets for ad-hoc tracking).*
   - *When two sources both claim authoritativeness, surface as an ambiguity, not a silent pick.*
   - *Tables that don't reconcile with any other source remain as `UnreconciledTable` — that's correct, not a failure.*
   - *Canonical names are business words ("Customer", "Order"), not technical ("contacts_table_v2").*
   - *Merge strategy is `PREFERRED_SOURCE` by default; `LATEST_WRITE_WINS` only when both sources have explicit `updated_at`; `UNION` only when the user gains by seeing both; `AGGREGATE` requires explicit field-level list.*
   - *Primary-key strategy: prefer `GENERATED_UUID` for new reconciled entities; `INHERIT_AUTHORITATIVE` only when the authoritative source has a stable, non-PII id.*

6. **Forbidden patterns**:
   - Do not assume two tables with the same name are the same entity. (Shopify `customers` ≠ Salesforce `Customer__c` unless overlap supports it.)
   - Do not skip authoritative-source rationale.
   - Do not auto-merge phone or email fields without normalization in `JoinKey.transformation`.
   - Do not invent reconciled entities the agent cannot defend with overlap evidence.
   - Do not output SQL.

7. **Examples** — at least three:
   - Single-source case (no reconciliation; trivially passes through).
   - Two-source case (Shopify customers + Mailchimp contacts → reconciled Customer with Mailchimp authoritative for marketing-consent).
   - Four-source case with one ambiguity (Stripe + Sheets + Notion + Mailchimp; Stripe authoritative for billing, Sheets for bookings, Notion for notes, Mailchimp for newsletter — with one ambiguous case where two sources both have address fields, surfaced for clarification).

### 3.4 `overlap.py` — Deterministic Pre-Computation

The agent doesn't see raw rows. The orchestrator pre-computes overlap statistics:

```python
async def compute_overlap_stats(
    sources: list[ClassifiedSource],
    connector_registry: ConnectorRegistry,
    tokens: dict[str, ConnectorToken],
) -> list[OverlapStat]:
    """For every candidate join key pair across sources, sample
    up to N rows from each and compute value-overlap rate after
    normalization (lowercase + trim for strings, exact match for ids)."""
    ...
```

This is **deterministic structural pre-work**, not heuristics. The agent sees: *"Stripe.customer.email and Notion.Customers.Email overlap at 0.87 across 200 sampled rows (after lowercase + trim)."* The agent then *decides* if 0.87 is enough evidence to call them the same entity (a high-stakes semantic call worthy of reasoning-tier).

This split is exactly the agentic-bar contract: deterministic helpers feed evidence; agents decide meaning.

### 3.5 The Output Validator

```python
@agent.output_validator
async def validate(ctx: RunContext[AgentDeps], out: EntityReconciliationPlan) -> EntityReconciliationPlan:
    # Every reconciled entity must have ≥1 contributing source
    for ent in out.reconciled_entities:
        if not ent.contributing_sources:
            raise ModelRetry(f"{ent.canonical_name} has no contributing sources.")

    # Every reconciled entity with ≥2 contributors must have ≥1 join key
    for ent in out.reconciled_entities:
        if len([s for s in ent.contributing_sources if s.role != SourceRole.LOG_ONLY]) >= 2:
            if not ent.join_keys:
                raise ModelRetry(f"{ent.canonical_name} reconciles ≥2 sources but has no join_keys.")

    # Every column mapping must reference real classified columns
    classified_set = {(s.connector_name, c.table_name, c.column_name)
                      for s in ctx.deps.classified_sources for c in s.classified_columns}
    for ent in out.reconciled_entities:
        for cm in ent.column_mappings:
            for contrib in cm.contributions:
                key = (contrib.connector_name, ent.contributing_sources[0].source_table, contrib.source_column)
                if not any(k[0] == contrib.connector_name and k[2] == contrib.source_column for k in classified_set):
                    raise ModelRetry(f"Column mapping references unknown source column: {contrib}")

    # Authoritative source must be one of the contributing connectors
    for ent in out.reconciled_entities:
        contributing_connectors = {s.connector_name for s in ent.contributing_sources}
        for col, conn in ent.conflict_policy.authoritative_source.items():
            if conn not in contributing_connectors:
                raise ModelRetry(f"Authoritative source {conn} for {ent.canonical_name}.{col} is not a contributing source.")

    # Recommendation confidence must be present for every ambiguity
    for amb in out.ambiguities:
        if amb.recommendation_confidence < 0.0 or amb.recommendation_confidence > 1.0:
            raise ModelRetry(f"Ambiguity {amb.target} has invalid recommendation_confidence.")

    return out
```

## 4. Design Patterns Applied

| Pattern | Where | Why |
|---|---|---|
| **Strategy** | `MergeStrategy` enum + per-entity choice | Multiple merge approaches; agent picks per case. |
| **Specification** | `OverlapStat` deterministic pre-work | Evidence-feeding pattern: structural helpers feed; agent reasons. |
| **Gate-driven repair** | Validator → `ModelRetry` → manager escalation | Bad reconciliation poisons everything downstream; gate is strict. |
| **Authoritative-source policy** | Per-field `ConflictPolicy` | Standard CRDT-style conflict resolution made explicit. |

## 5. Test Plan

- **Validator tests**: every `ModelRetry` branch fires under the wrong shape.
- **TestModel-driven tests**: for each fixture, inject canonical output and assert downstream `PhysicalSchemaArchitect` receives valid input.
- **Property test**: `reconciled_entities ∪ unreconciled_tables` covers every input source table — nothing is silently dropped.
- **Conflict-resolution test**: when two sources both could be authoritative, the agent must surface an `Ambiguity` (not silently pick).
- **Overlap-stat fidelity test**: the deterministic `compute_overlap_stats` is tested independently with golden fixtures (input rows → expected overlap rates).
- **Edge cases**: zero-source case raises `BF-AGENT-ENT-002`; single-source case produces a plan with one `ReconciledEntity` per table and no ambiguities; four-source case with one ambiguity produces exactly one `Ambiguity`.
- **Coverage**: 92%.

## 6. Error Codes

| Code | Condition | Recovery |
|---|---|---|
| `BF-AGENT-ENT-001` | Output validation failed after retries | Manager escalates tier; if still failing, surfaces as `BF-AGENT-005`. |
| `BF-AGENT-ENT-002` | Empty input (no classified sources) | Caller guards; should never reach agent. |
| `BF-AGENT-ENT-003` | Authoritative source not in contributing sources | Validator raises; agent re-runs. |
| `BF-AGENT-ENT-004` | Ambiguity has no recommendation | Validator raises; agent re-runs. |
| `BF-AGENT-ENT-005` | Reconciled entity has no join keys but has 2+ active sources | Validator raises; agent re-runs. |
| `BF-AGENT-ENT-006` | Unbreakable ambiguity escalation | Manager surfaces to `ClarificationAgent` for user input. |

## 7. Dependencies

- [`AGENT-COL`](AGENT-COL.md) — produces the per-source classified columns.
- [`CONN-FRAMEWORK`](CONN-FRAMEWORK.md) — the deterministic `compute_overlap_stats` reads from connectors.
- [`IR-CORE`](IR-CORE.md) — feeds `PhysicalSchemaArchitect` which builds final IR from the reconciliation plan.

## 8. Milestone

- **M1:** **single-source path only** — the agent runs but trivially: each source's tables become unreconciled; the plan contains one `ReconciledEntity` per table with one contributor. This unblocks the full v1 graph end-to-end.
- **M2:** **full multi-source path** — `compute_overlap_stats` lit up; the agent reasons over 2+ sources. **The unified-Customer-card moment lands here.** Validation conversation: a real SMB drops Excel + Stripe + (Shopify or Sheets) and sees the moat.
- **M3:** add Notion + Mailchimp; richer authoritative-source rationale; conflict policy honors connector "domain authority" hints.
- **M4+:** feedback flywheel — when users override the reconciler's choices (e.g., "no, Mailchimp is authoritative for email, not Stripe"), corrections feed `feedback_events` and curated examples improve the prompt.
