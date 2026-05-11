"""Agent runtime + artifact-centric agents.

- `types.py`        — typed contracts (AgentSpec, AgentRunResult, ModelTier, ...)
- `registry.py`     — name-keyed AgentSpec lookup + register_agent decorator
- `model_routing.py`— tier → model name resolution via env config
- `factory.py`      — cached pydantic_ai.Agent construction
- `runtime.py`      — AgentRuntime.run(...) — repair loop + concurrency + tracing

Artifact-centric agents live under `app/agents/<name>/` and register themselves
at module import via `register_agent(...)`.
"""

from app.agents import source_agent  # noqa: F401
from app.agents import reconciliation_agent  # noqa: F401
from app.agents import schema_agent  # noqa: F401
from app.agents import insight_agent  # noqa: F401
