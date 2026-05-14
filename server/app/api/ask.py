"""The /ask endpoint — primary conversational surface of the OS.

User POSTs a question, the orchestrator picks tools, gathers real data,
synthesizes an answer. Returns the answer + tool-call trace for transparency.

Stateless v1. Conversation persistence (multi-turn) lands in a follow-up
sprint via a Conversation model.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.auth.dependencies import require_auth
from app.core.context import TenantCtx
from app.orchestrator import AskResult, ask

router = APIRouter(tags=["ask"])


class AskRequest(BaseModel):
    question: str = Field(min_length=1, max_length=2000)


@router.post("", response_model=AskResult)
async def ask_endpoint(
    body: AskRequest,
    tenant: Annotated[TenantCtx, Depends(require_auth)],
) -> AskResult:
    return await ask(body.question, tenant)
