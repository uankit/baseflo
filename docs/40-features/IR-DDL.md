# `IR-DDL` — DDL Compiler (Postgres)

Status: M1. Compiles `SchemaIR` to safe Postgres DDL via SQLGlot. Deterministic, dialect-pluggable, zero string concatenation.

---

## 1. Overview

`IR-DDL` is the deterministic compiler that emits `CREATE TABLE`, foreign keys, indexes, check constraints, and audit-timestamp triggers from a unified `SchemaIR`. It uses SQLGlot's expression API to construct SQL — never string templates, never f-strings, never user input embedded in raw SQL. The compiler also computes a parallel migration script (`alembic`-shaped) and a hash for change detection.

The compiler is the only path from IR to physical schema. `PhysicalSchemaArchitect` produces the IR; this module turns it into something a database executes. No agent emits SQL; no SQL is generated outside this module.

## 2. High-Level Design

```
SchemaIR
    │
    ▼
┌──────────────────────┐    ┌──────────────────┐
│  DDL Emitter         │───▶│  SQLGlot AST     │
│  (table-by-table)    │    │  (typed)         │
└──────────┬───────────┘    └────────┬─────────┘
           │                         │
           ▼                         ▼
   migration script          rendered DDL string
   (alembic-style)           (per-dialect: postgres v1)
           │                         │
           └─────────┬───────────────┘
                     ▼
       Data plane runner: emit_ddl(ir, ctx)
```

## 3. Low-Level Design

### 3.1 Module Layout

```
server/app/engines/schema/ddl/
├── __init__.py
├── compiler.py             # entrypoint: compile_ir(ir) -> EmissionResult
├── postgres/
│   ├── __init__.py
│   ├── tables.py           # emit_table(ir: TableIR) -> ASTNode
│   ├── columns.py          # column type mapping; default values; nullability
│   ├── relationships.py    # FK constraints; on_delete handling
│   ├── indexes.py
│   ├── checks.py           # CHECK_ENUM, CHECK_RANGE, CHECK_POSITIVE, CURRENCY_CONSIST
│   ├── triggers.py         # audit-timestamp triggers (created_at/updated_at)
│   └── identifiers.py      # identifier safety: re.compile(r'^[a-z][a-z0-9_]*$') quoted otherwise
├── migration/
│   ├── __init__.py
│   ├── diff_to_alembic.py  # SchemaDiff → alembic migration ops
│   └── templates.py
├── dialect.py              # DialectAdapter Protocol (postgres v1; mysql/snowflake later)
└── tests/
    ├── test_postgres_ddl_round_trip.py     # IR → DDL → parse-back → IR round-trip
    ├── test_constraint_emission.py
    ├── test_identifier_safety.py
    ├── test_migration_generation.py
    └── fixtures/                           # canonical IR fixtures + golden DDL outputs
```

### 3.2 Key Types

```python
class EmissionResult(BaseModel):
    sql: str
    ast_hash: str                             # SHA-256 of the canonical AST
    table_count: int
    relationship_count: int
    index_count: int
    constraint_count: int
    migration_script: MigrationScript
    warnings: list[EmissionWarning]

class MigrationScript(BaseModel):
    upgrade_ops: list[AlembicOp]
    downgrade_ops: list[AlembicOp]            # always populated; deterministic inverse

class DialectAdapter(Protocol):
    """Strategy for per-dialect emission. Postgres ships v1; MySQL/Snowflake later."""
    name: str
    def emit_create_table(self, table: TableIR) -> Expression: ...
    def emit_relationship(self, rel: RelationshipIR) -> Expression: ...
    def emit_check_constraint(self, table: str, constraint: CheckConstraint) -> Expression: ...
    def emit_index(self, idx: IndexIR) -> Expression: ...
    def emit_audit_triggers(self, table_name: str) -> list[Expression]: ...
```

### 3.3 Emission Rules

- Identifiers go through `identifiers.py` which uses `re.compile(r'^[a-z][a-z0-9_]*$')` (the only legitimate regex in the codebase per [`05-coding-rules.md` §1.2](../05-coding-rules.md)). Names that match are emitted bare; names that don't match are quoted (and a warning emitted because something upstream let through a non-conforming name).
- Money columns: `BIGINT NOT NULL` for `*_minor`, `CHAR(3) NOT NULL` for `*_currency`, `CHECK (*_minor >= 0)`, `CHECK (*_currency ~ '^[A-Z]{3}$')` (the only other legitimate regex — emitted into the database, not run in Python).
- Status columns: `TEXT NOT NULL CHECK (column IN ('value1', 'value2', ...))`.
- Audit timestamps: every table gets `created_at TIMESTAMPTZ NOT NULL DEFAULT now()` + `updated_at TIMESTAMPTZ NOT NULL DEFAULT now()` + a trigger that updates `updated_at` on row update.
- Primary keys: `UUID NOT NULL DEFAULT uuid_generate_v7()` (extension required).
- Foreign keys: emitted as named constraints (`fk_orders_customer`); on_delete from IR.
- Indexes: every FK column indexed automatically; explicit indexes from `IndexIR` added.
- All DDL is wrapped in a single transaction by the data plane runner.

### 3.4 Migration Generation

`diff_to_alembic.py` takes a `SchemaDiff` (computed by `transforms.py`) and produces typed `AlembicOp` records (add_column, drop_column, alter_column, etc.). The downgrade is the reverse. Migration scripts are written to `server/migrations/versions/` with a deterministic filename derived from the diff hash.

### 3.5 Dialect Pluggability

For v1, only `PostgresAdapter` ships. The `DialectAdapter` protocol is defined and the compiler entrypoint takes an adapter parameter. Adding MySQL or Snowflake (M5+) is a new module under `ddl/<dialect>/` implementing the protocol; no engine code changes.

## 4. Design Patterns Applied

| Pattern | Where | Why |
|---|---|---|
| **Strategy** | `DialectAdapter` protocol | Multi-dialect support without core changes. |
| **Visitor** | DDL emitter walks IR tree | Each IR node maps to AST emission. |
| **Builder** | SQLGlot expression construction | No string concatenation; AST-first. |
| **Pipe / Functional Composition** | `compile_ir` is a pipeline of pure transforms | Test-friendly. |

## 5. Test Plan

- Round-trip property test: every fixture IR → DDL → SQLGlot parse → re-derive IR → equal to original. Critical correctness check.
- Identifier-safety test: an IR with a bad column name fails compilation with `BF-SCHEMA-005`; warning is emitted on quoted names.
- Constraint-emission test: each `ConstraintKind` produces the correct DDL fragment.
- Migration-generation test: parent IR + diff → upgrade + downgrade ops; applied + reverted leaves DB unchanged.
- Execution test: emitted DDL applied against a real Postgres in CI succeeds.
- Coverage: 95%.

## 6. Error Codes

| Code | Condition | Recovery |
|---|---|---|
| `BF-SCHEMA-EMIT-001` | IR fails pre-emission validation | Refuse compilation; surface the failing IR validator. |
| `BF-SCHEMA-EMIT-002` | Unsupported physical type for dialect | Refuse; ops alert; future dialect support. |
| `BF-SCHEMA-EMIT-003` | Identifier requires quoting | Warning, not error; emitted with quotes. |
| `BF-SCHEMA-EMIT-004` | DDL fails to apply against database | Surface DB error verbatim with the offending statement. |

## 7. Dependencies

[`IR-CORE`](IR-CORE.md), `engines/schema/transforms.py`, SQLGlot, alembic.

## 8. Milestone

- **M0**: skeleton; ships round-trip tests against single-source fixtures.
- **M1**: full Postgres emission; integrated with hosted data plane.
- **M2**: migration generation for refinements (`SchemaDiff` → alembic ops).
- **M5+**: MySQL adapter; Snowflake adapter.
