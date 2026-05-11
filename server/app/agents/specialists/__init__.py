"""Specialist agents.

Each specialist lives in its own subpackage (`<role>/`) with the agreed
anatomy per docs/03-agentic-workflow.md §3:

    <role>/
    ├── __init__.py     # registers the AgentSpec at import
    ├── types.py        # input/output Pydantic models
    ├── prompt.py       # the INSTRUCTIONS string (≥200 words)
    ├── evidence.py     # deterministic helper(s) — when applicable
    └── agent.py        # AgentSpec + output validator + register_agent()
"""

from __future__ import annotations

# Importing each specialist registers it with the AgentRegistry.
# CoherenceGate's validator inspects the registry at agent-run time (not import
# time), so order doesn't strictly matter here, but we keep registrations sorted
# by name for predictable boot logs.
from app.agents.specialists import (  # noqa: F401
    cardinality_resolver,
    change_planner,
    clarification,
    coherence_gate,
    column_classifier,
    constraint_proposer,
    entity_reconciler,
    impact_analyzer,
    intent_interpreter,
    kpi_planner,
    physical_schema_architect,
)
