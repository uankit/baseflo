"""Natural language query engine."""

from __future__ import annotations

from typing import Any

from pydantic_ai import Agent

from app.config import get_settings
from app.core.errors import BasefloError

settings = get_settings()

QUERY_PROMPT = """
You are an expert SQL analyst. Given a business question and a database schema,
write a correct PostgreSQL query that answers the question.

Rules:
- Use ONLY tables and columns that exist in the schema.
- Prefer explicit JOINs over subqueries when possible.
- Handle NULLs gracefully.
- Add clear column aliases.
- Return JSON with: sql (the query), title (short description), description (what it computes).

If the question is ambiguous, ask for clarification instead of guessing.
"""


class QueryEngine:
    """NL → SQL → Results."""

    def __init__(self) -> None:
        self._agent = Agent(
            model=settings.openai_model,
            system_prompt=QUERY_PROMPT,
        )

    async def execute(self, question: str, schema: dict[str, Any]) -> dict[str, Any]:
        """Generate SQL, run it, return narrative + data."""
        if not settings.openai_api_key:
            raise BasefloError(
                message="OpenAI API key not configured",
                error_code="BF-BRAIN-001",
                status_code=503,
            )

        # TODO: build agent input with schema context
        # TODO: execute generated SQL via session
        # TODO: format results
        return {
            "question": question,
            "sql": "SELECT 1",
            "title": "Placeholder",
            "description": "Query engine not yet wired",
            "rows": [],
        }
