# `AGENT-COL` — ColumnClassifier

Status: M1. The foundation agent. Every downstream specialist depends on its typed output.

---

## 1. Overview

`ColumnClassifier` reads a single source schema (one connector's introspection output, plus sample rows) and produces a typed classification per column: semantic type (`PII_EMAIL`, `MONEY`, `STATUS`, `IDENTITY`, etc.), canonical name, user-facing label, and — when applicable — currency, minor-unit assumption, observed enum values, and PII-masking default. It is *the* agent that lets every other agent and the deterministic compilers reason about meaning rather than parse strings.

It does NOT decide cross-source identity (that's `EntityReconciler`), it does NOT decide relationships or cardinality (`CardinalityResolver`), and it does NOT propose KPIs (`KPIPlanner`). It only classifies columns within a single source's tables.

## 2. High-Level Design

```
SourceSchema (from connector)        ┌──────────────────────────┐
+ sample_rows (≤50 per table)        │  ColumnClassifier        │
            │                        │  (model_tier: balanced)  │
            ▼                        └────────────┬─────────────┘
┌─────────────────────────┐                       │
│ ColumnClassifierInput   │  ─────────────────▶   │  output_validator
│  source_name, tables    │                       │  (raises ModelRetry on
│  columns + samples      │                       │   conflicts/missing fields)
└─────────────────────────┘                       │
                                                  ▼
                                  ┌──────────────────────────────┐
                                  │ ColumnClassifierOutput       │
                                  │  classified[*]:              │
                                  │   canonical_name             │
                                  │   semantic_type              │
                                  │   confidence                 │
                                  │   currency, enum_values,     │
                                  │   minor_unit, mask_default   │
                                  └──────────────────────────────┘
                                              │
                                              ▼
                              feeds: EntityReconciler, ConstraintProposer,
                                     PhysicalSchemaArchitect, KPIPlanner
```

## 3. Low-Level Design

### 3.1 Module Layout

```
server/app/agents/specialists/column_classifier/
├── __init__.py
├── agent.py            # Agent definition, prompt, output_validator, registry registration
├── prompt.py           # The INSTRUCTIONS block (≥200 words; persona + rules + schema + examples + forbidden)
├── types.py            # ColumnClassifierInput, ColumnClassifierOutput, ClassifiedColumn
└── tests/
    ├── test_validator.py
    ├── test_prompt_invariants.py        # asserts prompt has required sections
    ├── test_with_test_model.py          # canonical fixture inputs → asserted outputs via TestModel
    └── fixtures/
        ├── ecommerce_products.json
        ├── ecommerce_customers.json
        └── yoga_studio_bookings.json
```

### 3.2 Key Types

```python
# types.py
class SampleColumn(BaseModel):
    name: str                              # source's native column name
    source_type: str                       # connector's native type
    nullable: bool
    sample_values: list[str | int | float | bool | None]  # ≤30 values
    description: str | None = None
    primary_key_member: bool = False

class SampleTable(BaseModel):
    name: str
    columns: list[SampleColumn]
    estimated_row_count: int | None = None

class ColumnClassifierInput(BaseModel):
    connector_name: str                    # "shopify", "postgres", "my_internal_crm"
    source_name: str                       # human-friendly (display name of the source)
    tables: list[SampleTable]              # one classifier run per source

class ClassifiedColumn(BaseModel):
    table_name: str
    column_name: str                       # source's native name
    canonical_name: str = Field(pattern=r"^[a-z][a-z0-9_]*$", min_length=1, max_length=63)
    label: str
    semantic_type: SemanticType            # imported from engines/schema/enums.py
    physical_type: PhysicalType
    nullable: bool
    confidence: Annotated[float, Field(ge=0.0, le=1.0)]
    rationale: str                         # one sentence; goes into trace, not user-surfaced
    pii_masked_by_default: bool = False
    enum_values: list[str] | None = None   # only when semantic_type == STATUS
    currency: str | None = None            # ISO 4217; only when semantic_type == MONEY
    is_minor_unit: bool = False            # only when semantic_type == MONEY
    minor_unit_assumption: str | None = None  # plain English; e.g., "Stripe-style cents"

class ColumnClassifierOutput(BaseModel):
    classified: list[ClassifiedColumn]
    assumptions: list[str] = []            # cross-cutting assumptions (e.g., "USD for all money")
```

### 3.3 The Prompt (in `prompt.py`)

Required sections per [`03-agentic-workflow.md` §6.2](../03-agentic-workflow.md):

1. **Persona** — *"You are Baseflo's column classifier."*
2. **Job** — one paragraph; classify columns from a single source.
3. **Inputs** — typed shape reference.
4. **Output schema** — `ColumnClassifierOutput` signature embedded.
5. **Rules** (5–7 bullets):
   - Classify by observed evidence, not by source-table or column *name* alone.
   - Use sample values to determine MONEY currency and minor-unit assumption.
   - For STATUS, list observed enum values; if you can't determine them from samples, return CATEGORY with low confidence.
   - For PII, set `pii_masked_by_default = True`.
   - Canonical names are snake_case, descriptive (`customer_email` not `c_em`).
   - When unsure, return CATEGORY or FREE_TEXT with confidence < 0.6 — `EntityReconciler` and `ConstraintProposer` will refine.
6. **Forbidden patterns:**
   - Do not use the source-table name to imply schema (`"orders"` table doesn't mean an `order_status` column is STATUS).
   - Do not assume `_cents` suffix means MONEY without sample-value evidence.
   - Do not invent columns the source doesn't have.
   - Do not output SQL.
7. **Examples** — at least one canonical input → output mapping. Two for ambiguous cases (e.g., a "phone" column that could be `pii_phone` or `category`).

The prompt is ≥200 words. The static prefix (persona + rules + forbidden + examples) is stable across invocations; only the user input (`ColumnClassifierInput.model_dump_json()`) varies — cache-aligned per [`02-tech-stack.md` LLM Provider Strategy](../02-tech-stack.md).

### 3.4 The Output Validator

```python
@agent.output_validator
async def validate(ctx: RunContext[AgentDeps], out: ColumnClassifierOutput) -> ColumnClassifierOutput:
    seen: set[tuple[str, str]] = set()
    for c in out.classified:
        # Uniqueness within (table, canonical_name)
        key = (c.table_name, c.canonical_name)
        if key in seen:
            raise ModelRetry(f"Duplicate canonical_name in {c.table_name}: {c.canonical_name}.")
        seen.add(key)

        # Money requires currency + minor-unit assumption
        if c.semantic_type == SemanticType.MONEY:
            if not c.currency:
                raise ModelRetry(f"{c.canonical_name} is MONEY; supply currency (ISO 4217).")
            if c.minor_unit_assumption is None:
                raise ModelRetry(f"{c.canonical_name} is MONEY; supply minor_unit_assumption.")

        # Status requires enum_values
        if c.semantic_type == SemanticType.STATUS and not c.enum_values:
            raise ModelRetry(f"{c.canonical_name} is STATUS; supply enum_values from sample data.")

        # PII columns must be masked by default
        if c.semantic_type.startswith("pii_") and not c.pii_masked_by_default:
            raise ModelRetry(f"{c.canonical_name} is {c.semantic_type}; pii_masked_by_default must be True.")

        # Confidence must be plausible: PII or MONEY at confidence < 0.7 is suspicious
        if c.semantic_type in (SemanticType.MONEY, *PII_SEMANTIC_TYPES) and c.confidence < 0.7:
            raise ModelRetry(f"{c.canonical_name} typed as {c.semantic_type} at low confidence ({c.confidence}); reclassify or downgrade.")

    return out
```

The validator does **structural** checks. It does **not** double-guess the agent's classification. Semantic decisions stay in the prompt; the validator catches malformed shape only.

## 4. Design Patterns Applied

| Pattern | Where | Why |
|---|---|---|
| **Factory** | `Agent` instantiated via `_build_agent` cache | Reused across runs with same instructions. |
| **Strategy** (per tier) | `model_routing.py` resolves "balanced" tier model | Switch model without touching agent code. |
| **Validator-Driven Repair** | `@agent.output_validator` raises `ModelRetry` | Self-corrects malformed output before manager-level escalation. |

## 5. Test Plan

- **Validator tests** (`test_validator.py`):
  - Each `ModelRetry` branch fires under exactly the wrong shape.
  - Valid output passes through unchanged.
- **Prompt invariant tests** (`test_prompt_invariants.py`):
  - Prompt length ≥ 200 words.
  - Prompt contains persona / rules / forbidden / output-schema reference / ≥1 example.
  - Prompt does NOT interpolate user data (cache-alignment check).
- **TestModel-driven tests** (`test_with_test_model.py`):
  - Use Pydantic AI's `TestModel(custom_output_args=...)` to inject canonical outputs.
  - For each fixture in `fixtures/`, assert the call shape (input passed to TestModel) matches expected.
  - For each fixture, assert that downstream consumers (EntityReconciler input, etc.) receive valid input.
- **No real provider calls** in unit tests, ever.
- **Coverage**: 90%.

## 6. Error Codes

| Code | Condition | Recovery |
|---|---|---|
| `BF-AGENT-COL-001` | Output validation failed after retries | Manager escalates tier (balanced → reasoning); if still failing, surface as `BF-AGENT-005`. |
| `BF-AGENT-COL-002` | Input has zero tables | Caller (orchestrator) guards; this should never reach the agent. |
| `BF-AGENT-COL-003` | All sample columns are empty / no values | Connector layer issue; surfaces as `BF-CONN-NNN` upstream. |

## 7. Dependencies

- [`IR-CORE`](IR-CORE.md) — `SemanticType`, `PhysicalType` enums.
- [`CONN-FRAMEWORK`](CONN-FRAMEWORK.md) — produces `SourceSchema` + sample rows that become `ColumnClassifierInput`.

## 8. Milestone

- **M1:** full implementation, fixtures, tests, integrated into single-source data-architect graph.
- **M2:** runs once per connected source in multi-source flow; outputs aggregated into `EntityReconciler` input.
- **M3+:** prompt iterations driven by feedback flywheel (`feedback_events` → curated examples).
