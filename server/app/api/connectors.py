"""Connector routes — OAuth, connect, sync."""

from __future__ import annotations

import json
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy import select

from app.auth.dependencies import require_auth
from app.connect.google_sheets import GoogleSheetsConnector
from app.connect.registry import get as get_connector
from app.core.context import TenantCtx
from app.core.errors import BasefloError
from app.db.models import DataSource, Project, SyncRun
from app.db.session import open_session
from app.sync.engine import SyncEngine

router = APIRouter()


# ---------- Google Sheets OAuth ----------


@router.get("/google-sheets/auth-url")
async def google_sheets_auth_url(
    request: Request,
    project_id: UUID,
    spreadsheet_id: str | None = None,
    return_to: str | None = None,
    tenant: Annotated[TenantCtx, Depends(require_auth)] = None,
) -> dict[str, str]:
    """Get the Google OAuth consent URL."""
    connector = get_connector("google_sheets")
    assert isinstance(connector, GoogleSheetsConnector)

    from app.config import get_settings
    settings = get_settings()
    if settings.google_oauth_redirect_uri:
        redirect_uri = settings.google_oauth_redirect_uri
    else:
        # Backward-compatible with v1 Google Cloud Console registrations
        redirect_uri = settings.api_base_url.rstrip("/") + "/api/v1/oauth/google_sheets/callback"
    state = json.dumps({
        "project_id": str(project_id),
        "redirect_uri": redirect_uri,
        "spreadsheet_id": spreadsheet_id,
        "return_to": return_to,
    })

    url = connector.get_auth_url(redirect_uri=redirect_uri, state=state)
    return {"auth_url": url}


@router.get("/google-sheets/callback")
async def google_sheets_callback(
    request: Request,
    code: str,
    state: str,
) -> dict[str, Any]:
    """OAuth callback from Google. Exchanges code for tokens, creates DataSource."""
    state_data = json.loads(state)
    project_id = UUID(state_data["project_id"])
    redirect_uri = state_data["redirect_uri"]

    connector = get_connector("google_sheets")
    assert isinstance(connector, GoogleSheetsConnector)

    token_data = await connector.exchange_code(code, redirect_uri)

    access_token = token_data["access_token"]
    refresh_token = token_data.get("refresh_token")
    expires_in = token_data.get("expires_in", 3600)

    from datetime import UTC, datetime, timedelta
    expires_at = datetime.now(UTC) + timedelta(seconds=expires_in)

    # For MVP, we need the spreadsheet_id. In a real flow, the user would
    # select/paste this before or after OAuth. Here we'll accept it via query
    # or use a placeholder that the user updates later.
    # For now, store the tokens and mark as pending spreadsheet_id.
    async with open_session() as session:
        # Verify project exists
        project = await session.get(Project, project_id)
        if project is None:
            raise BasefloError(
                message="Project not found",
                error_code="BF-CONN-004",
                status_code=404,
            )

        source = DataSource(
            project_id=project_id,
            kind="google_sheets",
            name="Google Sheets",
            config={"spreadsheet_id": None},  # user must provide this next
            credentials={
                "access_token": access_token,
                "refresh_token": refresh_token,
                "expires_at": expires_at.isoformat(),
            },
            status="pending",
        )
        session.add(source)
        await session.flush()

    return {
        "message": "Google Sheets connected. Please provide a spreadsheet ID to complete setup.",
        "source_id": str(source.id),
        "status": "pending",
    }


# ---------- Source management ----------


class CreateSourceRequest(BaseModel):
    kind: str = Field(..., description="connector kind, e.g. google_sheets")
    name: str
    config: dict[str, Any] = Field(default_factory=dict)


class SourceResponse(BaseModel):
    id: str
    kind: str
    name: str
    status: str
    config: dict[str, Any]
    last_synced_at: str | None = None


@router.post("", response_model=SourceResponse)
async def create_source(
    body: CreateSourceRequest,
    project_id: UUID,
    tenant: Annotated[TenantCtx, Depends(require_auth)],
) -> SourceResponse:
    """Create or finalize a data source (e.g. attach spreadsheet_id after OAuth)."""
    async with open_session() as session:
        project = await session.get(Project, project_id)
        if project is None:
            raise BasefloError(
                message="Project not found",
                error_code="BF-CONN-004",
                status_code=404,
            )

        source = DataSource(
            project_id=project_id,
            kind=body.kind,
            name=body.name,
            config=body.config,
            credentials={},
            status="active",
        )
        session.add(source)
        await session.flush()

        # Auto-run first sync in background (MVP: fire-and-forget task)
        # TODO: use proper background worker

    return SourceResponse(
        id=str(source.id),
        kind=source.kind,
        name=source.name,
        status=source.status,
        config=source.config,
        last_synced_at=source.last_synced_at.isoformat() if source.last_synced_at else None,
    )


@router.get("")
async def list_sources(
    project_id: UUID,
    tenant: Annotated[TenantCtx, Depends(require_auth)],
) -> list[SourceResponse]:
    """List all data sources for a project."""
    async with open_session() as session:
        result = await session.execute(
            select(DataSource).where(DataSource.project_id == project_id)
        )
        sources = result.scalars().all()

    return [
        SourceResponse(
            id=str(s.id),
            kind=s.kind,
            name=s.name,
            status=s.status,
            config=s.config,
            last_synced_at=s.last_synced_at.isoformat() if s.last_synced_at else None,
        )
        for s in sources
    ]


# ---------- Sync ----------


@router.post("/{source_id}/sync")
async def sync_source(
    source_id: UUID,
    tenant: Annotated[TenantCtx, Depends(require_auth)],
) -> dict[str, Any]:
    """Trigger a manual sync of a data source."""
    async with open_session() as session:
        source = await session.get(DataSource, source_id)
        if source is None:
            raise BasefloError(
                message="Source not found",
                error_code="BF-CONN-005",
                status_code=404,
            )

        engine = SyncEngine(session)
        run = await engine.sync_source(source)

    return {
        "sync_run_id": str(run.id),
        "status": run.status,
        "rows_synced": run.rows_synced,
        "started_at": run.started_at.isoformat(),
        "finished_at": run.finished_at.isoformat() if run.finished_at else None,
    }
