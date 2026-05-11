# `AGENT-IMP` — ImpactAnalyzer

Status: M2. Computes the blast radius of a refinement: which artifacts change, what cascades, what stays the same.

---

## 1. Overview

Given a typed `RefinementIntent` and a parent `SchemaIR`, `ImpactAnalyzer` produces a structured `ImpactSummary` that lists every artifact affected (tables, columns, relationships, KPIs, dashboard charts, admin tabs, SDK methods, daily-digest sections) and how. It does **not** produce the change plan — that's `ChangePlanner`. It does **not** apply changes. Its single job is honest blast-radius accounting: *"Here is everything this change touches; user, you should know before you click Apply."*

The output drives the user-visible diff preview in the refinement panel.

## 2. High-Level Design

```
RefinementIntent + parent_ir + parent_kpis +
deterministic ReferenceGraph (computed)
                    │
                    ▼
        ┌──────────────────────────┐
        │  ImpactAnalyzer          │
        │  (model_tier: reasoning) │
        └────────────┬─────────────┘
                     │
                     ▼
              ImpactSummary (typed)
                     │
              ┌──────┴──────┐
              ▼             ▼
       diff renderer    ChangePlanner input
       (user-facing
        plain-language
        bullets)
```

## 3. Low-Level Design

### 3.1 Module Layout

```
server/app/agents/specialists/impact_analyzer/
├── __init__.py
├── agent.py
├── prompt.py
├── types.py
├── evidence.py            # ReferenceGraph: which KPIs reference which columns, etc.
└── tests/
    ├── test_validator.py
    ├── test_with_test_model.py
    └── fixtures/
        ├── add_wishlists_impact.json
        ├── remove_low_value_segment_impact.json
        ├── rename_customers_to_clients_impact.json
        └── split_orders_impact.json
```

### 3.2 Key Types

```python
class ReferenceGraph(BaseModel):
    """Deterministic: which artifacts reference which schema elements."""
    table_referenced_by_kpis: dict[str, list[str]]            # table_name -> [kpi_names]
    column_referenced_by_kpis: dict[str, list[str]]           # "table.column" -> [kpi_names]
    table_referenced_by_relationships: dict[str, list[str]]   # table_name -> [relationship_names]
    column_referenced_by_relationships: dict[str, list[str]]  # "table.column" -> [relationship_names]
    table_rendered_in_admin: dict[str, list[str]]             # table_name -> [tab_id]
    column_in_sdk: dict[str, list[str]]                       # "table.column" -> [sdk_method_signatures]

class ImpactSeverity(StrEnum):
    BREAKING            = "breaking"           # existing data or queries become invalid
    DEGRADING           = "degrading"          # works but quality drops (KPI loses precision)
    ADDITIVE            = "additive"           # new things only; nothing existing changes
    NONE                = "none"               # no observable impact

class ImpactedArtifact(BaseModel):
    kind: ArtifactKind                         # TABLE | COLUMN | RELATIONSHIP | KPI | ADMIN_TAB | SDK_METHOD | DIGEST_SECTION
    identifier: str                            # natural key
    severity: ImpactSeverity
    description: str                           # plain English; user-facing diff bullet
    propagation: list[str]                     # natural keys of downstream artifacts further affected

class ImpactAnalyzerInput(BaseModel):
    intent: RefinementIntent
    parent_ir: SchemaIR
    parent_kpis: list[KPIDefinition]
    reference_graph: ReferenceGraph

class ImpactSummary(BaseModel):
    impacted: list[ImpactedArtifact]
    additive_only: bool                        # True iff every impact is ADDITIVE/NONE
    user_visible_changes: list[str]            # plain-English bullets for the diff renderer
    backward_compatible: bool                  # SDK + persisted data still work
    rationale: str                             # trace only

class ImpactAnalyzerOutput(BaseModel):
    summary: ImpactSummary
```

### 3.3 Evidence-Feeding Helper

```python
def compute_reference_graph(ir: SchemaIR, kpis: list[KPIDefinition]) -> ReferenceGraph:
    """Walk the IR and KPI definitions to build the cross-reference index.
    Pure function over typed inputs; deterministic; cached per parent_ir hash."""
```

The agent reads the typed `ReferenceGraph` and the `RefinementIntent` and reasons: *"User wants to remove `customer.address` column. ReferenceGraph says: 3 KPIs reference it, 1 admin tab renders it, 2 SDK methods expose it. Severity: BREAKING for those 6 artifacts. Propagation: removing the column means those KPIs need to be reformulated, the admin column hidden, the SDK methods regenerate."*

### 3.4 The Prompt (key rules)

- Use `ReferenceGraph` as the authoritative reference index. Never manually re-walk the IR.
- For every artifact in `ReferenceGraph` referenced by the change target, include an `ImpactedArtifact` entry.
- Severity calibration:
  - REMOVE/RENAME of a column referenced by KPIs/SDK/admin → BREAKING.
  - MODIFY column type incompatibly → BREAKING.
  - ADD column to existing table → ADDITIVE (existing rows nullable; if NOT_NULL, surface as DEGRADING with default needed).
  - ADD entirely new entity → ADDITIVE.
  - SPLIT/MERGE → BREAKING by default; agent justifies if otherwise.
- `additive_only` is True iff every entry is ADDITIVE or NONE.
- `backward_compatible` is True iff every existing SDK method signature still resolves to typed columns post-change.
- Propagation chains: if removing column X breaks KPI Y, and KPI Y feeds dashboard chart Z and digest section W, list all four with their relationships.

Forbidden:
- Inventing impacts not present in `ReferenceGraph`.
- Marking BREAKING changes as ADDITIVE to "make the user comfortable."
- Vague descriptions. Every `description` must name the affected artifact and the user-visible effect ("Revenue this week KPI loses subscription billing breakdown" — not "KPI affected").

### 3.5 The Output Validator

```python
@agent.output_validator
async def validate(ctx: RunContext[AgentDeps], out: ImpactAnalyzerOutput) -> ImpactAnalyzerOutput:
    summary = out.summary

    # Every impacted artifact's identifier must exist in parent_ir / parent_kpis / known sdk methods
    valid_identifiers = _collect_all_identifiers(ctx.deps.parent_ir, ctx.deps.parent_kpis, ctx.deps.reference_graph)
    for a in summary.impacted:
        if a.identifier not in valid_identifiers and not _is_proposed_new(a, ctx.deps.intent):
            raise ModelRetry(f"Impacted artifact {a.identifier} not in parent and not proposed-new.")

    # additive_only consistency
    has_breaking_or_degrading = any(a.severity in (ImpactSeverity.BREAKING, ImpactSeverity.DEGRADING) for a in summary.impacted)
    if summary.additive_only and has_breaking_or_degrading:
        raise ModelRetry("additive_only=True but BREAKING/DEGRADING impacts present.")

    # backward_compatible consistency: any BREAKING SDK_METHOD impact ⇒ backward_compatible=False
    breaking_sdk = [a for a in summary.impacted if a.kind == ArtifactKind.SDK_METHOD and a.severity == ImpactSeverity.BREAKING]
    if breaking_sdk and summary.backward_compatible:
        raise ModelRetry("BREAKING SDK_METHOD impact present but backward_compatible=True.")

    # user_visible_changes must be non-empty unless additive_only and the only adds are internal
    if not summary.user_visible_changes:
        raise ModelRetry("user_visible_changes must list at least one bullet for the diff renderer.")

    return out
```

## 4. Design Patterns Applied

| Pattern | Where | Why |
|---|---|---|
| **Evidence-Feeding** | `evidence.py` → `ReferenceGraph` | Agent reads typed cross-reference facts; never recomputes. |
| **Specification** | Each `ArtifactKind` is a typed predicate the validator checks against the parent's enumerable artifact set | Catches phantom-artifact references early. |
| **Validator-Driven Repair** | `@agent.output_validator` | Catches additivity/backward-compatibility consistency violations. |

## 5. Test Plan

- Validator tests for each `ModelRetry` branch.
- Reference graph tests: golden fixtures (parent IR + KPIs → expected `ReferenceGraph`).
- TestModel-driven: ADD / REMOVE / RENAME / SPLIT / MERGE / MODIFY each produce the right impact set.
- Property test: every column referenced in `parent_kpis[*].formula` appears in `reference_graph.column_referenced_by_kpis`.
- Coverage: 92%.

## 6. Error Codes

| Code | Condition | Recovery |
|---|---|---|
| `BF-AGENT-IMP-001` | Validation failed after retries | Manager escalates tier. |
| `BF-AGENT-IMP-002` | Impacted artifact not in parent and not proposed-new | Validator raises. |
| `BF-AGENT-IMP-003` | additive_only inconsistent with severity distribution | Validator raises. |
| `BF-AGENT-IMP-004` | backward_compatible inconsistent with SDK breaking impacts | Validator raises. |
| `BF-AGENT-IMP-005` | Empty user_visible_changes | Validator raises. |

## 7. Dependencies

[`AGENT-INT`](AGENT-INT.md), [`IR-CORE`](IR-CORE.md), [`AGENT-KPI`](AGENT-KPI.md), [`AGENT-PHYS`](AGENT-PHYS.md).

## 8. Milestone

- **M2**: full implementation; powers the diff preview in the refinement panel.
- **M3+**: flywheel — when users repeatedly apply changes the impact analyzer marked BREAKING (suggesting we underestimated user appetite for change), reweight severity calibration through curated examples.
