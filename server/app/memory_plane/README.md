# Memory Plane

The Memory Plane stores autonomous business memory.

It does not store chat history, raw rows, analysis results, or model messages.
Pydantic AI can manage transient agent/message history separately. This package
owns only durable business semantics that should shape future scans.

Examples:

- business summary
- business entities and KPIs
- asset roles
- field roles
- confirmed relationships
- validated recurring pattern types

Flow:

```text
Agent Plane structured artifacts
-> memory candidates
-> confidence/user-memory guard
-> business_memories table
-> loaded into future CanonicalContextPack.memories
```

Rules:

- No raw row values.
- No narrative-only memories.
- No execution-plane access.
- No agent message history.
- User-authored memory beats lower-confidence autonomous memory.
