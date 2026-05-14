"""Tool registry — the product surface for the LLM orchestrator.

Each Tool is a generic primitive with a typed input schema and an async
`run(input, ctx)` function. The orchestrator composes specific analyses by
chaining tools, not by calling named domain helpers (no `compute_runway`,
no `compute_funnel` — those are brittle catalog entries).

Adding new capability = adding a tool here. The set should stay small (~15-25
across the whole product) and primitive (generic across data shapes).
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel

from app.core.context import TenantCtx
from app.core.errors import NotFoundError


_registry: dict[str, "Tool"] = {}


@dataclass(frozen=True, slots=True)
class Tool:
    name: str
    description: str
    input_schema: type[BaseModel]
    run: Callable[[BaseModel, TenantCtx], Awaitable[Any]]


def register(tool: Tool) -> None:
    if tool.name in _registry:
        raise ValueError(f"Tool '{tool.name}' already registered")
    _registry[tool.name] = tool


def get(name: str) -> Tool:
    tool = _registry.get(name)
    if tool is None:
        raise NotFoundError(
            message=f"Unknown tool: {name}",
            code="UNKNOWN_TOOL",
            status_hint=404,
        )
    return tool


def list_tools() -> list[Tool]:
    return list(_registry.values())


# Import tool modules to trigger registration via side-effect.
# To add a new tool category: create app/tools/<name>.py with `register(...)`
# calls and add one import line below.
from app.tools import data as _data  # noqa: F401, E402
from app.tools import operating as _operating  # noqa: F401, E402
