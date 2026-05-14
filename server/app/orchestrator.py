"""LLM orchestrator — the brain that uses the tool registry.

Takes a user question, invokes OpenAI with our tools available, executes tool
calls in parallel where possible, loops until the LLM returns a final answer
(or hits the iteration cap). The LLM never computes anything itself — it only
picks which tools to call and composes the final response from their results.

For v1: stateless. Each `/ask` call is one independent Q&A; no cross-call
conversation memory. Multi-turn conversations come later via a Conversation
model and a `conversation_id` parameter.
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

from openai import AsyncOpenAI
from pydantic import BaseModel

from app.config import get_settings
from app.core.context import TenantCtx
from app.core.errors import AppError, AuthError
from app.tools import Tool, get as _get_tool, list_tools

logger = logging.getLogger("baseflo.orchestrator")

_MAX_ITERATIONS = 10

_SYSTEM_PROMPT = """\
You are Baseflo — an adaptive operating intelligence layer for the user's business.

Your job is to help the user understand business state from connected data:
what exists, what changed, why it matters, and what next move is supported by
evidence. You are not a spreadsheet copilot, dashboard template, or autonomous
employee cosplay. You ground every answer in real data and keep risky action
recommendations approval-oriented.

How to work:
1. If you don't know what data exists, call `get_operating_brief` or
   `list_assets` first. They return queryable tables, roles, insights, actions,
   and columns.
2. If you need more detail about a specific table (row count, exact types),
   call `profile_asset`.
3. To get real numbers, emit a typed `AnalysisGraph` through
   `execute_analysis_graph`. Never write raw SQL. The runtime is the only layer
   allowed to compile and execute queries.
4. Once you have enough data, respond in plain English. Be concise and
   direct. Cite the table(s) you used.

Rules:
- Always get numbers from tool results. Never invent or estimate.
- Never output SQL or ask for SQL execution. Use AnalysisGraph plans only.
- Do not force the user into business templates. Infer only from connected data.
- If a question can't be answered with the available data, say so plainly
  and suggest what the user could connect.
- If you recommend an action, state the evidence and frame it as a proposed
  next step requiring approval.
- Keep answers short. The user wants the number, the why, and the next move.
"""


# ---------- Result schemas ----------


class ToolCallTrace(BaseModel):
    name: str
    arguments: dict[str, Any]
    result: Any | None = None
    error: str | None = None


class AskResult(BaseModel):
    answer: str
    artifacts: list[dict[str, Any]] = []
    tool_calls: list[ToolCallTrace]
    iterations: int
    model: str
    warning: str | None = None


# ---------- Internals ----------


def _settings():
    return get_settings()


def _ensure_client() -> AsyncOpenAI:
    settings = _settings()
    if settings.openai_api_key is None:
        raise AuthError(
            message="OpenAI is not configured (set OPENAI_API_KEY)",
            code="OPENAI_NOT_CONFIGURED",
            status_hint=503,
        )
    return AsyncOpenAI(api_key=settings.openai_api_key.get_secret_value())


def _openai_tool_schema(tool: Tool) -> dict[str, Any]:
    schema = tool.input_schema.model_json_schema()
    params: dict[str, Any] = {
        "type": "object",
        "properties": schema.get("properties", {}),
    }
    required = schema.get("required")
    if required:
        params["required"] = required
    return {
        "type": "function",
        "function": {
            "name": tool.name,
            "description": tool.description,
            "parameters": params,
        },
    }


async def _execute_tool_call(
    name: str, args_json: str, ctx: TenantCtx,
) -> tuple[Any | None, str | None]:
    try:
        args = json.loads(args_json) if args_json else {}
    except json.JSONDecodeError as exc:
        return None, f"invalid JSON arguments: {exc}"

    try:
        tool = _get_tool(name)
    except AppError as exc:
        return None, exc.message

    try:
        parsed = tool.input_schema.model_validate(args)
        result = await tool.run(parsed, ctx)
        return result, None
    except Exception as exc:
        logger.exception("tool %s failed", name)
        return None, f"{type(exc).__name__}: {exc}"


def _serialize_for_llm(value: Any) -> str:
    """JSON-serialize a tool result for the LLM. Truncate gracefully on overrun."""
    try:
        text = json.dumps(value, default=str)
    except Exception as exc:
        return json.dumps({"error": f"serialization failed: {exc}"})
    # Soft cap so a wide query doesn't blow the context window.
    if len(text) > 60_000:
        return json.dumps({
            "truncated": True,
            "preview": text[:60_000],
            "note": "Result truncated. Add filters or LIMIT to your query.",
        })
    return text


# ---------- Public entrypoint ----------


async def ask(question: str, ctx: TenantCtx) -> AskResult:
    """Run the tool-use loop until the model returns a final text answer."""
    client = _ensure_client()
    model = _settings().openai_model
    tools_schema = [_openai_tool_schema(t) for t in list_tools()]

    messages: list[dict[str, Any]] = [
        {"role": "system", "content": _SYSTEM_PROMPT},
        {"role": "user", "content": question},
    ]
    trace: list[ToolCallTrace] = []

    for iteration in range(_MAX_ITERATIONS):
        response = await client.chat.completions.create(
            model=model,
            messages=messages,
            tools=tools_schema,
            tool_choice="auto",
        )
        msg = response.choices[0].message

        if msg.tool_calls:
            # Append assistant turn (with tool_calls) verbatim — the API requires
            # this exact format before tool result messages.
            messages.append({
                "role": "assistant",
                "content": msg.content,
                "tool_calls": [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments,
                        },
                    }
                    for tc in msg.tool_calls
                ],
            })

            # Execute all tool calls from this turn in parallel.
            results = await asyncio.gather(*[
                _execute_tool_call(
                    tc.function.name, tc.function.arguments or "{}", ctx,
                )
                for tc in msg.tool_calls
            ])

            for tc, (result, error) in zip(msg.tool_calls, results):
                try:
                    parsed_args = json.loads(tc.function.arguments or "{}")
                except Exception:
                    parsed_args = {}

                trace.append(ToolCallTrace(
                    name=tc.function.name,
                    arguments=parsed_args,
                    result=result,
                    error=error,
                ))

                payload = result if error is None else {"error": error}
                messages.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": _serialize_for_llm(payload),
                })
        else:
            return AskResult(
                answer=(msg.content or "").strip() or "(no answer produced)",
                artifacts=[],
                tool_calls=trace,
                iterations=iteration + 1,
                model=model,
            )

    return AskResult(
        answer="The agent reached the iteration limit without producing a final answer.",
        artifacts=[],
        tool_calls=trace,
        iterations=_MAX_ITERATIONS,
        model=model,
        warning="max_iterations_reached",
    )
