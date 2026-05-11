# `AGENT-INT` — IntentInterpreter

Status: M2. Parses English-language refinement requests into typed intent — never with keyword matching.

---

## 1. Overview

`IntentInterpreter` turns the user's plain-English refinement ("Add wishlists — customers should save products they like") into a typed `RefinementIntent` object. It is the entry point of the refinement graph and replaces the keyword-detection anti-pattern flagged in the original Baseflo audit (`if "delete" in text → DELETE`).

The agent identifies intent kind (ADD / REMOVE / RENAME / SPLIT / MERGE / MODIFY), targets (entities / attributes / relationships / KPIs), and proposed details (new entity name, fields hinted, relationship hinted). It does **not** decide whether the change is feasible — that's `ImpactAnalyzer`. It does **not** produce the typed delta — that's `ChangePlanner`. Its single output is a faithful interpretation of what the user wants.

## 2. High-Level Design

```
User refinement input (English) + parent_ir
                    │
                    ▼
        ┌──────────────────────────┐
        │  IntentInterpreter       │
        │  (model_tier: balanced)  │
        └────────────┬─────────────┘
                     │
                     ▼
              RefinementIntent (typed)
                     │
                     ▼
              fed to ImpactAnalyzer
```

## 3. Low-Level Design

### 3.1 Module Layout

```
server/app/agents/specialists/intent_interpreter/
├── __init__.py
├── agent.py
├── prompt.py
├── types.py
└── tests/
    ├── test_validator.py
    ├── test_with_test_model.py
    └── fixtures/
        ├── add_wishlists.json
        ├── remove_low_value_segment.json
        ├── rename_customers_to_clients.json
        ├── split_orders_into_quotes_and_invoices.json
        ├── ambiguous_intent.json
        └── nonsense_input.json
```

### 3.2 Key Types

```python
class IntentKind(StrEnum):
    ADD                = "add"                        # add new entity / column / relationship / KPI
    REMOVE             = "remove"                     # remove existing
    RENAME             = "rename"                     # rename existing
    SPLIT              = "split"                      # one entity becomes many
    MERGE              = "merge"                      # many become one
    MODIFY             = "modify"                     # change properties (cardinality, constraint, type)
    UNKNOWN            = "unknown"                    # could not interpret confidently

class IntentTarget(StrEnum):
    ENTITY             = "entity"
    COLUMN             = "column"
    RELATIONSHIP       = "relationship"
    KPI                = "kpi"
    DASHBOARD          = "dashboard"

class IntentInterpreterInput(BaseModel):
    text: str = Field(min_length=3, max_length=2000)
    parent_ir: SchemaIR
    parent_kpis: list[KPIDefinition]

class IntentDetail(BaseModel):
    """Free-form details typed lightly. The agent fills in what it confidently parsed."""
    proposed_name: str | None = None                  # snake_case for new entities
    proposed_label: str | None = None                 # display label
    fields_hinted: list[FieldHint] = []
    relationships_hinted: list[RelationshipHint] = []
    target_existing: list[str] = []                   # for REMOVE / RENAME / MODIFY: existing names

class FieldHint(BaseModel):
    name: str                                         # snake_case suggestion
    purpose: str                                      # plain English from user input

class RelationshipHint(BaseModel):
    from_entity: str
    to_entity: str
    description: str                                  # plain English

class RefinementIntent(BaseModel):
    kind: IntentKind
    target: IntentTarget
    detail: IntentDetail
    confidence: Annotated[float, Field(ge=0.0, le=1.0)]
    rationale: str                                    # trace only
    user_quote: str                                   # the user's words; preserved for downstream agents

class IntentInterpreterOutput(BaseModel):
    intent: RefinementIntent
    needs_clarification: bool                         # true if confidence < threshold or kind == UNKNOWN
    clarification_question: str | None = None         # plain English; surfaces via ClarificationAgent flow
```

### 3.3 The Prompt (key rules)

≥250 words. Sections:

1. **Persona**: *"You are Baseflo's refinement intent interpreter. You translate plain-English refinement requests into typed intent — never by keyword matching, always by reasoning over meaning."*

2. **Job**: detailed paragraph emphasizing semantic understanding.

3. **Inputs**: typed shapes; parent IR is context.

4. **Output schema**: `RefinementIntent` reference.

5. **Rules**:
   - Identify *kind* by the user's underlying request, not by surface words. *"I want to exclude low-value customers"* could be REMOVE or MODIFY (filter); reason about which.
   - Identify *target* (entity / column / relationship / KPI / dashboard).
   - For ADD requests, propose snake_case name and plain-language description.
   - For REMOVE requests, identify the existing target by name (must match parent IR).
   - For RENAME requests, capture both old and new names.
   - For SPLIT/MERGE, capture all participating entities.
   - For MODIFY, capture which property changes (cardinality, constraint, etc.).
   - If you cannot confidently parse: `kind = UNKNOWN`, `confidence < 0.5`, `needs_clarification = True`, supply a single plain-English clarifying question.
   - Always preserve `user_quote` verbatim for `ImpactAnalyzer` and `ChangePlanner`.

6. **Forbidden**:
   - Never detect intent by keyword (`"add" in text → ADD`). Reason over meaning.
   - Never invent entity names not implied by the user's words.
   - Never produce a typed intent at confidence > 0.7 for ambiguous text.
   - Never output structural detail (FK direction, cardinality numbers) — that's `ImpactAnalyzer` and `ChangePlanner`.

7. **Examples** — six (one per `IntentKind` plus one ambiguous):
   - "Add wishlists — customers should save products they like" → ADD entity, target=ENTITY, name=`wishlists`, relationship hinted (Customer ↔ Wishlist ↔ Product).
   - "Remove the low-value customer segment" → MODIFY (filter), target=ENTITY, target_existing=[customers].
   - "Rename customers to clients" → RENAME, target=ENTITY.
   - "Split orders into quotes and invoices" → SPLIT, two new entities.
   - "Make subscription monthly instead of annual" → MODIFY, target=COLUMN/KPI.
   - "I want to know about churn" → UNKNOWN; ask "Do you mean (a) add a churn-rate KPI, (b) add a customer-status field tracking churn, or (c) both?"

### 3.4 The Output Validator

```python
@agent.output_validator
async def validate(ctx: RunContext[AgentDeps], out: IntentInterpreterOutput) -> IntentInterpreterOutput:
    intent = out.intent

    # If kind == UNKNOWN, must request clarification
    if intent.kind == IntentKind.UNKNOWN and not out.needs_clarification:
        raise ModelRetry("UNKNOWN intent requires needs_clarification=True with a question.")

    # If needs_clarification, must provide question
    if out.needs_clarification and not out.clarification_question:
        raise ModelRetry("needs_clarification=True requires clarification_question.")

    # REMOVE/RENAME/MODIFY targets must reference existing names in parent_ir
    if intent.kind in (IntentKind.REMOVE, IntentKind.RENAME, IntentKind.MODIFY):
        if not intent.detail.target_existing:
            raise ModelRetry(f"{intent.kind} requires detail.target_existing.")
        existing_names = _collect_existing_names(ctx.deps.parent_ir, ctx.deps.parent_kpis, intent.target)
        for t in intent.detail.target_existing:
            if t not in existing_names:
                raise ModelRetry(f"target_existing references unknown {intent.target}: {t}")

    # ADD must propose a name
    if intent.kind == IntentKind.ADD and not intent.detail.proposed_name:
        raise ModelRetry("ADD requires detail.proposed_name (snake_case).")

    # user_quote is non-empty
    if not intent.user_quote.strip():
        raise ModelRetry("user_quote must be preserved verbatim.")

    return out
```

## 4. Design Patterns Applied

| Pattern | Where | Why |
|---|---|---|
| **Strategy** | `IntentKind` + `IntentTarget` enums | Typed dispatch downstream. |
| **Validator-Driven Repair** | `@agent.output_validator` | Catches malformed intent shapes early. |

(No evidence-feeding helper here — the input is unstructured English; the agent's reasoning is the work. Helpers would amount to NLP heuristics, which are forbidden.)

## 5. Test Plan

- Validator tests for every `ModelRetry` branch.
- TestModel-driven coverage for each `IntentKind` + ambiguous case.
- Property test: `target_existing` references in REMOVE/RENAME/MODIFY always resolve to real parent_ir/kpi names.
- Coverage: 90%.

## 6. Error Codes

| Code | Condition | Recovery |
|---|---|---|
| `BF-AGENT-INT-001` | Validation failed after retries | Manager escalates tier. |
| `BF-AGENT-INT-002` | UNKNOWN intent without clarification question | Validator raises. |
| `BF-AGENT-INT-003` | REMOVE/RENAME/MODIFY target not in parent | Validator raises. |
| `BF-AGENT-INT-004` | ADD missing proposed_name | Validator raises. |

## 7. Dependencies

[`IR-CORE`](IR-CORE.md), [`AGENT-KPI`](AGENT-KPI.md) (parent KPIs as additional target context), [`AGENT-CLAR`](AGENT-CLAR.md) (escalation path on ambiguity).

## 8. Milestone

- **M2**: full implementation; refinement panel UI consumes the output.
- **M3+**: flywheel — user clarifications and corrections feed example bank.
