# Execution Plane

The Execution Plane is the deterministic bridge between Agent Plane planning
and Agent Plane result reasoning.

Input:

- `organization_id`
- `AnalysisGraphPlan`

Output:

- `AnalysisResultRef`

Responsibilities:

- Resolve asset ids and field ids to canonical DuckDB tables/columns.
- Normalize the agent-emitted graph before compilation.
- Validate source, select, filter, join, aggregate, rank, and limit operators.
- Require relationship evidence before joining fields across assets.
- Compile the generic operator graph into DuckDB SQL.
- Parse and render every executable statement through `sqlglot`.
- Reject non-SELECT statements, multi-statement SQL, and table references
  outside the execution catalog.
- Execute safely through the canonical DuckDB mirror.
- Return result preview, row count, lineage, operation count, and source
  footprint.

Non-responsibilities:

- No agents.
- No SQL from agents.
- No business interpretation.
- No plan repair or fallback guesses.
- No user-facing prose.

Package shape:

```text
resolver.py      database ids -> ExecutionCatalog
normalizer.py    AnalysisGraphPlan -> NormalizedExecutionPlan
compiler.py      NormalizedExecutionPlan -> CompiledAnalysisPlan
guard.py         sqlglot read-only/catalog guard
runtime.py       DuckDB execution -> AnalysisResultRef
```
