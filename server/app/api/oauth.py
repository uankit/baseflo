"""OAuth callback routes — backward-compatible with v1 Google Cloud Console registrations."""

from __future__ import annotations

import json
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Request

from app.connect.google_sheets import GoogleSheetsConnector
from app.connect.registry import get as get_connector
from app.core.errors import BasefloError
from app.db.models import DataSource, Project
from app.db.session import open_session

router = APIRouter()


@router.get("/google_sheets/callback")
async def google_sheets_callback(
    request: Request,
    code: str,
    state: str,
) -> dict[str, Any]:
    """OAuth callback from Google. Exchanges code for tokens, creates DataSource.

    Backward-compatible with v1 redirect_uri:
      http://localhost:8000/api/v1/oauth/google_sheets/callback
    """
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
            kind="google_sheets",
            name="Google Sheets",
            config={"spreadsheet_id": None},
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
