# `REFINEMENT` — Refinement Pipeline + Versioning

Status: M2. Combines `REF-PANEL` + `REF-PIPELINE` + `REF-DIFF` + `REF-ROLLBACK` + `ADMIN-VERSIONS` from [`30-features.md`](../30-features.md). The English-language evolution loop.

---

## 1. Overview

Every change to a project after initial generation goes through this pipeline. The user types intent in plain English; agents parse, analyze impact, plan changes; a deterministic compiler applies the plan; an immutable child version commits with parent lineage. Rollback is a one-click operation.

The pipeline replaces the old keyword-detection refinement (audit-flagged) with the agent-driven `IntentInterpreter → ImpactAnalyzer → ChangePlanner → CoherenceGate` flow.

## 2. High-Level Design

```
User input ("Add wishlists")            ┌──────────────────┐
       │                                │ Refinement Panel │
       └──────────────────────────────▶ │ (right rail)     │
                                        └────────┬─────────┘
                                                 │ POST /refinements
                                                 ▼
                                       ┌──────────────────────┐
                                       │ Refinement Saga      │
                                       └──────────┬───────────┘
                                                  │
                       ┌──────────────────────────┼──────────────────────────┐
                       ▼                          ▼                          ▼
              IntentInterpreter         ImpactAnalyzer              ChangePlanner
                       │                          │                          │
                       └──────────────────────────┼──────────────────────────┘
                                                  ▼
                            apply_diff(parent_ir, plan) → child_ir
                                                  │
                                                  ▼
                                          CoherenceGate
                                                  │
                                       passed? commit child version
                                                  │
                                                  ▼
                                       SSE: artifact.ready (new version)
                                                  │
                                                  ▼
                                       Admin UI auto-upgrades; SDK regenerates
```

## 3. Low-Level Design

### 3.1 Module Layout

```
server/app/services/refinement/
├── __init__.py
├── service.py              # RefinementService.execute(command) -> result
├── saga.py                 # RefinementSaga (forward + compensating actions)
├── diff_renderer.py        # ChangePlan -> plain-English bullets for UI preview
├── version_repo.py         # project_versions persistence + lineage
└── tests/
    ├── test_service.py
    ├── test_saga_compensation.py
    └── test_diff_renderer.py

client/apps/web/src/features/refinement/
├── components/
│   ├── RefinementPanel.tsx       # right-rail UI; English input + diff preview + apply
│   ├── DiffPreview.tsx
│   ├── VersionHistory.tsx        # browse versions; rollback action
│   └── ConflictResolver.tsx      # when refinement intent has unresolvable ambiguity
└── hooks/
    └── useRefinement.ts
```

### 3.2 Key Types

```python
class RefineProjectCommand(BaseModel):
    project_id: UUID
    parent_version_id: UUID
    intent_text: str
    actor: ActorRef
    idempotency_key: str

class RefineProjectResult(BaseModel):
    refinement_id: UUID
    child_version_id: UUID | None       # None until applied
    intent: RefinementIntent
    impact: ImpactSummary
    change_plan: ChangePlan
    diff_bullets: list[str]             # plain-English summary for UI
    status: RefinementStatus            # PROPOSED | APPLIED | DISCARDED | FAILED

class RefinementSaga:
    """Saga steps with compensators. See 50-design-patterns.md §9."""
    steps = [
        Step(forward="interpret_intent",   compensator=None),
        Step(forward="analyze_impact",     compensator=None),
        Step(forward="plan_change",        compensator=None),
        Step(forward="apply_diff_to_child_ir",   compensator="discard_child"),
        Step(forward="run_coherence_gate", compensator="discard_child"),
        Step(forward="emit_ddl_diff",      compensator="rollback_ddl"),
        Step(forward="commit_version",     compensator="hard_delete_child"),
        Step(forward="invalidate_caches",  compensator=None),
        Step(forward="notify_clients",     compensator=None),
    ]
```

### 3.3 The Two-Phase UX

**Phase 1 — Propose.** User types refinement; `IntentInterpreter` + `ImpactAnalyzer` + `ChangePlanner` run. The user sees a diff preview (plain-English bullets) and can:
- **Apply** → commit the new version.
- **Edit intent** → re-runs the pipeline.
- **Discard** → drop the proposal.

The proposed plan is persisted in `refinements` table with status `PROPOSED`; not yet committed to `project_versions`.

**Phase 2 — Apply.** User clicks Apply. Saga executes from `apply_diff_to_child_ir` onward. On success, status flips to `APPLIED`, `child_version_id` populated, `current_version_id` on the project switches to the new version. On failure, compensators run in reverse; status flips to `FAILED`; user sees the error.

### 3.4 Diff Renderer (Plain-English)

`diff_renderer.py` turns the typed `ChangePlan` into user-readable bullets:

- `ADD_TABLE(wishlists, ...)` → *"Add a Wishlists table for customers to save products."*
- `ADD_RELATIONSHIP(customers ↔ wishlists, 1..*)` → *"Each customer can have many wishlist entries."*
- `ADD_KPI("Wishlist conversion rate", ...)` → *"Track how often wishlist additions become orders."*
- `MODIFY_KPI("Revenue", ...)` → *"Update Revenue to include wishlist-driven sales."*
- `RENAME_TABLE(customers → clients)` → *"Rename Customers to Clients across the workspace, including 4 KPIs and 2 admin tabs."*

Renderer is deterministic (no LLM); each `ChangeOp` has a template + parameter substitution. The user-facing description was decided by `ChangePlanner` and lives in `payload.rationale`; the renderer formats it.

### 3.5 Version Lineage + Rollback

Every project has a single `current_version_id`. Refinements create child versions with `parent_version_id` set. Rollback to a prior version:
1. Sets `current_version_id` to the prior version.
2. Emits a typed `RolledBackEvent` audit row.
3. Re-emits DDL for the prior version (idempotent — DDL operations are versioned by hash).
4. Invalidates SDK caches.

Versions are immutable once committed. Rollback never deletes a version.

### 3.6 Refinement Panel UI

Right-rail collapsible panel, available on every workspace screen. Single text input + Submit. Loading state shows the SSE-streamed pipeline progress. Diff preview appears as a structured list with severity-colored bullets (BREAKING red, DEGRADING yellow, ADDITIVE green). Apply button is disabled if any BREAKING change requires a clarification first.

## 4. Design Patterns Applied

| Pattern | Where | Why |
|---|---|---|
| **Command** | `RefineProjectCommand` | Idempotent, replayable, auditable. |
| **Saga / Compensating Action** | Multi-step with rollback path | Refinement spans LLM calls + DB transactions; sagas give atomicity at a higher level. |
| **Two-Phase Commit (UX-level)** | Propose → Apply | User sees impact before committing. |
| **Template Method** | Diff renderer per `ChangeOp` | Each op kind has its own bullet template. |

## 5. Test Plan

- Unit: each saga step + compensator.
- Integration: full Propose → Apply → child version committed; Propose → Discard → no version change.
- Failure: `CoherenceGate` rejects child; saga compensates; user sees clear error.
- Rollback: child version → parent; prior version's data unchanged; admin UI re-renders.
- Property: `apply_diff(parent, plan)` always produces a valid IR (verified by `ChangePlanner.validator` already; here we cover the full pipeline).
- Coverage: 92%.

## 6. Error Codes

| Code | Condition | Recovery |
|---|---|---|
| `BF-REFINE-001` | Idempotency conflict | 409; client refreshes. |
| `BF-REFINE-002` | Intent unparseable; clarification required | UI surfaces clarification question. |
| `BF-REFINE-003` | Apply failed (DDL or coherence) | Saga compensates; user sees error. |
| `BF-REFINE-004` | Rollback failed (DDL inverse failed) | Operator alert; manual intervention. |
| `BF-REFINE-005` | Concurrent refinement on same project | Serialize via project lock; second waits. |

## 7. Dependencies

[`AGENT-INT`](AGENT-INT.md), [`AGENT-IMP`](AGENT-IMP.md), [`AGENT-CHG`](AGENT-CHG.md), [`AGENT-COHE`](AGENT-COHE.md), [`IR-CORE`](IR-CORE.md), [`IR-DDL`](IR-DDL.md), [`JOBS-AND-SSE`](JOBS-AND-SSE.md).

## 8. Milestone

- **M2**: full implementation; refinement panel ships; "Add wishlists" round-trip works.
- **M3**: rollback + version compare UI.
- **M4+**: side-by-side version diff visualization; refinement templates ("Add subscriptions" with multi-step plan).
