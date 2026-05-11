# `AGENT-CLAR` — ClarificationAgent

Status: M1. The preflight gate. Asks at most three blocking business questions before generation starts; never interrupts mid-flight.

---

## 1. Overview

`ClarificationAgent` is the only agent that can interrupt the user. It runs once at the start of every project build (and every refinement) and decides whether the user's intent is unambiguous enough to proceed. If it is, generation proceeds without user friction. If it isn't, the agent emits up to **three** plain-English questions whose answers will resolve a *blocking* business decision. Mid-flight uncertainty becomes typed assumptions and warnings, never user interruption (per [`01-architecture.md` §10](../01-architecture.md)).

The agent owns one judgment: *"Is there a business decision I cannot make on my behalf without making things worse if I'm wrong?"* It does not ask modeling questions, technical questions, or stylistic preference questions.

## 2. High-Level Design

```
┌──────────────────────────────────────────────────┐
│ Project intake (description + optional sources): │
│   description: str                               │
│   classified_sources: list[ClassifiedSource]?    │
└──────────────────────┬───────────────────────────┘
                       │
                       ▼
        ┌──────────────────────────┐
        │  ClarificationAgent      │
        │  (model_tier: fast)      │
        └────────────┬─────────────┘
                     │
                     ▼
        ┌──────────────────────────────────┐
        │ ClarificationOutput              │
        │   questions: list[Question]      │   # 0..3
        │   blocking: bool                 │
        │   rationale: str                 │   # trace only
        └────────────┬─────────────────────┘
                     │
              ┌──────┴──────┐
              ▼             ▼
         questions=[]   questions=[…]
              │             │
              ▼             ▼
       generation    SSE: clarification.required
       proceeds      → user answers in chat
                     → resume from this gate
```

## 3. Low-Level Design

### 3.1 Module Layout

```
server/app/agents/specialists/clarification/
├── __init__.py
├── agent.py
├── prompt.py
├── types.py
├── evidence.py            # deterministic helper: signals about description quality
└── tests/
    ├── test_validator.py
    ├── test_with_test_model.py
    └── fixtures/
        ├── clear_description.json
        ├── ambiguous_pricing_model.json
        ├── ambiguous_b2b_vs_b2c.json
        ├── connected_sources_no_questions.json
        └── too_thin_description.json
```

### 3.2 Key Types

```python
class ClarificationInput(BaseModel):
    description: str                                  # raw user input
    classified_sources: list[ClassifiedSource] = []   # if user already connected sources
    parent_ir: SchemaIR | None = None                 # for refinements
    refinement_intent: str | None = None              # for refinements
    description_signals: DescriptionSignals           # from evidence.py

class DescriptionSignals(BaseModel):
    word_count: int
    has_business_noun: bool                           # heuristic-free: agent will judge meaning
    references_pricing_words: bool                    # "subscription" / "one-time" / "free" present
    references_user_types: bool                       # "customers" / "members" / "patients" / etc.
    references_offering: bool                         # "products" / "services" / "bookings" / etc.

class Question(BaseModel):
    text: str = Field(min_length=10, max_length=200)
    business_topic: BusinessTopic                     # PRICING_MODEL | USER_TYPES | OFFERING_TYPE | LIFECYCLE | OTHER
    options: list[str] | None = None                  # if multiple-choice; max 4 options

class ClarificationOutput(BaseModel):
    questions: list[Question] = Field(max_length=3)
    blocking: bool                                    # questions are blocking iff len > 0
    rationale: str                                    # trace only; not user-visible
```

### 3.3 Evidence-Feeding Helper (`evidence.py`)

Deterministic signals about the description, computed before the agent runs:

```python
def compute_description_signals(text: str) -> DescriptionSignals:
    """Tokenize, count, and check for noun-phrase presence using
    a curated business-vocabulary list (NOT regex on raw text;
    spaCy or stanza for tokenization). Returns typed facts only."""
```

These signals are facts. The agent decides their meaning. ("16 words and pricing-words present? Probably enough. 4 words and no offering reference? Almost certainly need a clarification.")

### 3.4 The Prompt

≥250 words. Sections per [`03-agentic-workflow.md` §6.2](../03-agentic-workflow.md):

1. **Persona**: *"You are Baseflo's clarification agent. You decide whether the user has provided enough business context to generate a meaningful workspace, or whether you must ask up to three blocking questions first."*
2. **Job**: detailed paragraph emphasizing *only blocking business decisions matter*.
3. **Inputs**: typed shapes summarized.
4. **Output schema**: `ClarificationOutput` reference.
5. **Rules**:
   - Ask **only** when not asking would produce a worse workspace than asking.
   - Maximum three questions.
   - Plain business language. No modeling, schema, or technical jargon.
   - Prefer multiple-choice (`options`) over free-text when the choice is finite.
   - Each question must target a distinct `business_topic`.
   - If the user already connected sources, treat sample data as primary evidence; ask less.
   - If `parent_ir` is set (refinement), constrain questions to the refinement's scope.
6. **Forbidden**:
   - Never ask "what tables do you want?" or "what fields should X have?" — those are the architect agents' jobs.
   - Never ask preference questions ("dark mode?", "what color?").
   - Never ask more than three.
   - Never ask the same question across topics.
7. **Examples** — three:
   - Clear description → `[]`.
   - Ambiguous pricing → one question with options [`subscription`, `one-time`, `both`].
   - Multi-faceted ambiguity → three distinct questions.

### 3.5 The Output Validator

```python
@agent.output_validator
async def validate(ctx: RunContext[AgentDeps], out: ClarificationOutput) -> ClarificationOutput:
    if len(out.questions) > 3:
        raise ModelRetry("Max 3 clarification questions.")

    # Distinct topics
    topics = [q.business_topic for q in out.questions]
    if len(topics) != len(set(topics)):
        raise ModelRetry("Each question must target a distinct business_topic.")

    # blocking ↔ has questions
    if out.blocking and not out.questions:
        raise ModelRetry("blocking=True requires at least one question.")
    if not out.blocking and out.questions:
        raise ModelRetry("blocking=False requires zero questions.")

    # Multiple-choice options bounded
    for q in out.questions:
        if q.options is not None and (len(q.options) < 2 or len(q.options) > 4):
            raise ModelRetry(f"Options for question {q.text!r} must be 2..4 entries.")

    return out
```

## 4. Design Patterns Applied

| Pattern | Where | Why |
|---|---|---|
| **Evidence-Feeding** | `evidence.py` → `DescriptionSignals` | Agent reads typed facts about the description; never inspects raw text mechanically. |
| **Gate** | The agent itself acts as a preflight gate before the data-architect graph | Single decision point: proceed or block. |
| **Validator-Driven Repair** | `@agent.output_validator` → `ModelRetry` | Catches malformed shape (too many questions, blocking/empty mismatch). |

## 5. Test Plan

- **Validator tests**: each `ModelRetry` branch fires under exactly the wrong shape.
- **Evidence helper tests**: each `DescriptionSignals` field computed correctly across fixtures.
- **TestModel-driven coverage**:
  - Clear description fixture → `questions=[], blocking=False`.
  - Ambiguous-pricing fixture → exactly one question targeting `PRICING_MODEL` with options.
  - Multi-ambiguity fixture → three distinct-topic questions.
  - Already-connected-sources fixture → asks fewer or zero questions even with thin description.
  - Refinement fixture → questions scoped to refinement only.
- **Coverage**: 90%.

## 6. Error Codes

| Code | Condition | Recovery |
|---|---|---|
| `BF-AGENT-CLAR-001` | Output validation failed after retries | Manager escalates tier; if still failing, surfaces as `BF-AGENT-005`. |
| `BF-AGENT-CLAR-002` | More than 3 questions emitted | Validator raises; agent re-runs. |
| `BF-AGENT-CLAR-003` | Question targets modeling/technical concern (regex-free check via classifier in tests) | Validator raises in tests; production catches via prompt forbidden-pattern guidance. |

## 7. Dependencies

- [`AGENT-COL`](AGENT-COL.md) — when sources are connected, classified columns inform the agent's evidence.
- [`IR-CORE`](IR-CORE.md) — for refinement, parent IR scopes the question space.

## 8. Milestone

- **M1**: full implementation; fixtures cover the five canonical cases above.
- **M2**: extended for multi-source path; uses `EntityReconciler.ambiguities` as additional evidence (an unresolvable reconciliation may surface a clarification).
- **M3+**: feedback flywheel; questions users routinely skip become candidates for prompt-level deletion (we were over-asking).
