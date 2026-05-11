"""Natural language query routes."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.auth.dependencies import require_auth
from app.core.context import TenantCtx

router = APIRouter()


class QueryRequest(BaseModel):
    project_id: str
    question: str


class QueryResponse(BaseModel):
    answer: str
    sql: str | None = None


@router.post("/ask", response_model=QueryResponse)
async def ask_question(
    body: QueryRequest,
    tenant: Annotated[TenantCtx, Depends(require_auth)],
) -> QueryResponse:
    """Ask a natural language question about your data.

    MVP: returns a placeholder. The brain will answer here soon.
    """
    return QueryResponse(
        answer=f"You asked: '{body.question}'. The query engine is being wired up — check back soon!",
        sql=None,
    )
