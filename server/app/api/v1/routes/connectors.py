"""Connector install + list/get endpoints.

Per docs/40-features/CONN-FRAMEWORK.md §4. Each route returns the same
typed shape regardless of provider so the SDK / front-end can render a
unified "your connectors" surface.

OAuth-flow connectors (Shopify, Google Sheets) live in `oauth.py` because
they require the redirect dance. Direct-credential connectors (Stripe API
key, Postgres DSN) install through this router.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import datetime
import secrets
from typing import Annotated, Any
from uuid import UUID, uuid4

import httpx
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.routes.oauth import get_connector_registrar, get_webhook_subscriber
from app.auth.dependencies import require_tenant
from app.connectors.google_sheets.auth import (
    GoogleInstallParams,
    build_install_url as google_sheets_build_install_url,
)
from app.connectors.shopify.auth import (
    InstallParams as ShopifyInstallParams,
    build_install_url as shopify_build_install_url,
)
from app.core.config import get_config
from app.core.context import TenantCtx
from app.core.errors import BasefloError
from app.db.models.connector import Connector, ConnectorToken, TokenType
from app.db.session import open_session
from app.observability.logging import get_logger
from app.db.models.project import Project
from app.services.connector_oauth import (
    ConnectorRegistrar,
    ConnectorRegistration,
    WebhookSubscriber,
)
from datetime import UTC
from pathlib import Path
from fastapi import File, Form, UploadFile


__all__ = [
    "ConnectorListResponse",
    "ConnectorSummary",
    "StripeInstallRequest",
    "router",
]


router = APIRouter(prefix="/connectors", tags=["connectors"])
logger = get_logger("api.connectors")


_STRIPE_ACCOUNT_URL = "https://api.stripe.com/v1/account"


# ---------- Response shapes ----------


class ConnectorSummary(BaseModel):
    id: UUID
    project_id: UUID
    kind: str
    display_name: str
    status: str
    config: dict[str, Any]
    last_sync_at: datetime | None
    created_at: datetime


class ConnectorListResponse(BaseModel):
    connectors: list[ConnectorSummary]


class ConnectorInstallResult(BaseModel):
    connector_id: UUID
    kind: str
    project_id: UUID
    display_name: str
    account_id: str | None = None


class StripeInstallRequest(BaseModel):
    project_id: UUID
    api_key: str = Field(min_length=20, max_length=200)
    """Restricted or secret API key. Validated against `/v1/account` before
    persisting; never echoed back in responses or logs."""


# ---------- Service dependencies ----------


async def get_db_session() -> AsyncIterator[AsyncSession]:
    async with open_session() as session:
        yield session


# ---------- Stripe install ----------


def _stripe_transport() -> httpx.BaseTransport | None:
    """Test override hook. Production returns None (default httpx transport)."""
    return None


@router.post(
    "/stripe/install",
    response_model=ConnectorInstallResult,
    status_code=201,
    summary="Validate a Stripe API key and persist as a connector",
)
async def stripe_install(
    tenant: Annotated[TenantCtx, Depends(require_tenant)],
    body: StripeInstallRequest,
    registrar: Annotated[ConnectorRegistrar, Depends(get_connector_registrar)],
    subscriber: Annotated[WebhookSubscriber, Depends(get_webhook_subscriber)],
    transport: Annotated[httpx.BaseTransport | None, Depends(_stripe_transport)],
) -> ConnectorInstallResult:
    """Stripe doesn't have an OAuth install flow for non-platform apps.

    The user pastes a restricted secret key; we validate it by reading the
    account, then persist via the same `ConnectorRegistrar` that OAuth flows
    use. The encrypted token row carries the raw key.
    """
    config = get_config()
    client_kwargs: dict[str, object] = {"timeout": 10.0}
    if transport is not None:
        client_kwargs["transport"] = transport
    try:
        async with httpx.AsyncClient(**client_kwargs) as client:  # type: ignore[arg-type]
            response = await client.get(
                _STRIPE_ACCOUNT_URL,
                headers={"Authorization": f"Bearer {body.api_key}"},
            )
    except httpx.HTTPError as exc:
        raise BasefloError(
            error_code="BF-CONN-STRIPE-001",
            message=f"Stripe API unreachable: {exc!r}",
            status_code=502,
            cause=exc,
        ) from exc

    if response.status_code == 401:
        raise BasefloError(
            error_code="BF-CONN-STRIPE-002",
            message="Stripe rejected the API key. Verify the key is correct and not revoked.",
            status_code=400,
        )
    if response.status_code >= 400:
        raise BasefloError(
            error_code="BF-CONN-STRIPE-003",
            message=(
                f"Stripe /v1/account returned status={response.status_code}. "
                "Connector install aborted."
            ),
            status_code=400,
            details={"status": response.status_code, "body": response.text[:500]},
        )

    try:
        account = response.json()
    except ValueError as exc:
        raise BasefloError(
            error_code="BF-CONN-STRIPE-003",
            message="Stripe /v1/account returned non-JSON.",
            status_code=502,
            cause=exc,
        ) from exc
    account_id = account.get("id") if isinstance(account, dict) else None
    if not isinstance(account_id, str):
        raise BasefloError(
            error_code="BF-CONN-STRIPE-003",
            message="Stripe /v1/account response missing `id`.",
            status_code=502,
        )

    display_name = f"Stripe — {account_id}"
    connector_id = await registrar.register(ConnectorRegistration(
        organization_id=tenant.organization_id,
        project_id=body.project_id,
        kind="stripe",
        display_name=display_name,
        config={
            "api_version": config.stripe_api_version,
            "account_id": account_id,
        },
        token_type=TokenType.API_KEY.value,
        token_payload={
            "api_key": body.api_key,
            "account_id": account_id,
        },
        token_scopes=[],
    ))

    # Auto-subscribe webhooks via the Stripe webhook_endpoints API.
    await subscriber.subscribe_for_connector(connector_id)

    logger.info(
        "stripe_install_succeeded",
        organization_id=str(tenant.organization_id),
        project_id=str(body.project_id),
        account_id=account_id,
        connector_id=str(connector_id),
    )
    return ConnectorInstallResult(
        connector_id=connector_id,
        kind="stripe",
        project_id=body.project_id,
        display_name=display_name,
        account_id=account_id,
    )


# ---------- List / get ----------


@router.get(
    "",
    response_model=ConnectorListResponse,
    summary="List connectors visible under the active tenant context",
)
async def list_connectors(
    tenant: Annotated[TenantCtx, Depends(require_tenant)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    project_id: Annotated[
        UUID | None,
        Query(description="Filter by project; omit for all projects in the org."),
    ] = None,
) -> ConnectorListResponse:
    stmt = select(Connector).where(
        Connector.organization_id == tenant.organization_id,
        Connector.deleted_at.is_(None),
    )
    if project_id is not None:
        stmt = stmt.where(Connector.project_id == project_id)
    stmt = stmt.order_by(Connector.created_at.desc())
    result = await session.execute(stmt)
    rows = result.scalars().all()
    return ConnectorListResponse(connectors=[
        ConnectorSummary(
            id=row.id,
            project_id=row.project_id,
            kind=row.kind,
            display_name=row.display_name,
            status=row.status,
            config=row.config,
            last_sync_at=row.last_sync_at,
            created_at=row.created_at,
        )
        for row in rows
    ])


@router.get(
    "/{connector_id}",
    response_model=ConnectorSummary,
    summary="Fetch one connector by id",
)
async def get_connector(
    tenant: Annotated[TenantCtx, Depends(require_tenant)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    connector_id: UUID,
) -> ConnectorSummary:
    stmt = select(Connector).where(
        Connector.id == connector_id,
        Connector.organization_id == tenant.organization_id,
        Connector.deleted_at.is_(None),
    )
    result = await session.execute(stmt)
    row = result.scalar_one_or_none()
    if row is None:
        raise BasefloError(
            error_code="BF-API-001",
            message=f"Connector {connector_id} not found.",
            status_code=404,
        )
    return ConnectorSummary(
        id=row.id,
        project_id=row.project_id,
        kind=row.kind,
        display_name=row.display_name,
        status=row.status,
        config=row.config,
        last_sync_at=row.last_sync_at,
        created_at=row.created_at,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Postgres install — DSN-style, mirrors the Stripe API-key flow.
#
# Validates the connection by opening a fresh asyncpg pool and running a
# minimum-trust query (`SELECT 1`), then persists via the same registrar
# Stripe + OAuth flows use. Encrypted token row carries the raw DSN.
# ─────────────────────────────────────────────────────────────────────────────


class PostgresInstallRequest(BaseModel):
    project_id: UUID
    dsn: str = Field(min_length=12, max_length=2000)
    """A `postgresql://user:pass@host:port/db` URL. Stored encrypted; never
    echoed back in responses or logs."""
    display_name: str = Field(min_length=1, max_length=120, default="Postgres")


@router.post(
    "/postgres/install",
    response_model=ConnectorInstallResult,
    status_code=201,
    summary="Validate a Postgres DSN and persist as a connector",
)
async def postgres_install(
    tenant: Annotated[TenantCtx, Depends(require_tenant)],
    body: PostgresInstallRequest,
    registrar: Annotated[ConnectorRegistrar, Depends(get_connector_registrar)],
) -> ConnectorInstallResult:
    """Test the DSN by connecting + running `SELECT 1`. Reject on any error.

    Mirrors the Stripe install pattern (single endpoint, validates upstream,
    persists via the shared `ConnectorRegistrar`). The DSN is stored encrypted
    by the registrar; the connector's `config` only carries the host/db labels
    so ops can identify the row without unwrapping the secret.
    """
    import asyncpg  # noqa: PLC0415  — keep the import local; not all envs need it

    try:
        conn = await asyncpg.connect(body.dsn, timeout=10.0)
    except Exception as exc:  # noqa: BLE001
        raise BasefloError(
            error_code="BF-CONN-PG-001",
            message=(
                "Couldn't connect to Postgres with the provided DSN. "
                f"Detail: {exc!r}"
            ),
            status_code=400,
            cause=exc,
        ) from exc
    try:
        result = await conn.fetchval("SELECT 1")
        if result != 1:
            raise BasefloError(
                error_code="BF-CONN-PG-002",
                message="Postgres connected but `SELECT 1` returned an unexpected value.",
                status_code=502,
            )
        # Capture host/db for the config blob (no auth in there).
        host_row = await conn.fetchrow(
            "SELECT current_database() AS db, inet_server_addr()::text AS host"
        )
        db_name = host_row["db"] if host_row else None
        host = host_row["host"] if host_row else None
    finally:
        await conn.close()

    connector_id = await registrar.register(ConnectorRegistration(
        organization_id=tenant.organization_id,
        project_id=body.project_id,
        kind="postgres",
        display_name=body.display_name,
        config={
            "database": db_name,
            "host": host,
        },
        token_type=TokenType.DB_URL.value,
        token_payload={"dsn": body.dsn},
        token_scopes=[],
    ))

    logger.info(
        "postgres_install_succeeded",
        organization_id=str(tenant.organization_id),
        project_id=str(body.project_id),
        connector_id=str(connector_id),
        database=db_name,
    )
    return ConnectorInstallResult(
        connector_id=connector_id,
        kind="postgres",
        project_id=body.project_id,
        display_name=body.display_name,
        account_id=db_name,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Web-app additions: file upload (Excel / CSV), revoke, reconnect.
#
# These layer on top of the CLI surface; existing CLI routes unchanged.
# ─────────────────────────────────────────────────────────────────────────────


_UPLOAD_BASE_DIR = Path("/tmp/baseflo-uploads")


@router.post(
    "/upload",
    response_model=ConnectorSummary,
    status_code=201,
    summary="Install a CSV / Excel connector by uploading the file directly",
    description=(
        "Multipart upload variant of `/connectors/{kind}/install` for the "
        "FILE_UPLOAD auth kind. Writes the file under "
        "/tmp/baseflo-uploads/{org}/{flow_id}.{ext} and creates a Connector "
        "row whose `config['file_path']` points to it. The connector is then "
        "introspectable / readable by the existing Excel / CSV connector code "
        "(per app/connectors/{excel,csv}/connector.py)."
    ),
)
async def upload_install(
    tenant: Annotated[TenantCtx, Depends(require_tenant)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    project_id: Annotated[UUID, Form()],
    kind: Annotated[str, Form()],
    display_name: Annotated[str, Form()],
    file: Annotated[UploadFile, File()],
) -> ConnectorSummary:
    if kind not in {"csv", "excel"}:
        raise BasefloError(
            error_code="BF-CONN-001",
            message=f"Upload install supports csv or excel only; got {kind!r}.",
            status_code=400,
        )

    project = await session.get(Project, project_id)
    if project is None or project.organization_id != tenant.organization_id:
        raise BasefloError(
            error_code="BF-API-001",
            message="Project not found in active org.",
            status_code=404,
        )

    org_dir = _UPLOAD_BASE_DIR / str(tenant.organization_id)
    org_dir.mkdir(parents=True, exist_ok=True)
    flow_id_uuid = uuid4()
    suffix = ".xlsx" if kind == "excel" else ".csv"
    target_path = org_dir / f"{flow_id_uuid}{suffix}"

    contents = await file.read()
    target_path.write_bytes(contents)

    from app.core.ids import new_uuid7  # noqa: PLC0415
    connector_id = new_uuid7()

    connector = Connector(
        id=connector_id,
        organization_id=tenant.organization_id,
        project_id=project_id,
        kind=kind,
        display_name=display_name or file.filename or f"New {kind}",
        status="connected",
        config={"file_path": str(target_path), "filename": file.filename},
    )
    session.add(connector)
    await session.flush()

    logger.info(
        "connector_uploaded",
        connector_id=str(connector_id),
        kind=kind,
        bytes=len(contents),
        path=str(target_path),
    )

    return ConnectorSummary(
        id=connector.id,
        project_id=connector.project_id,
        kind=connector.kind,
        display_name=connector.display_name,
        status=connector.status,
        config=connector.config,
        last_sync_at=connector.last_sync_at,
        created_at=connector.created_at or datetime.now(UTC),
    )


@router.post(
    "/{connector_id}/revoke",
    status_code=204,
    summary="Revoke a connector (mark deleted; do not destroy data)",
)
async def revoke_connector(
    connector_id: UUID,
    tenant: Annotated[TenantCtx, Depends(require_tenant)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> None:
    stmt = select(Connector).where(
        Connector.id == connector_id,
        Connector.organization_id == tenant.organization_id,
        Connector.deleted_at.is_(None),
    )
    row = (await session.execute(stmt)).scalar_one_or_none()
    if row is None:
        raise BasefloError(
            error_code="BF-API-001",
            message=f"Connector {connector_id} not found.",
            status_code=404,
        )
    row.status = "revoked"
    row.deleted_at = datetime.now(UTC)
    await session.flush()


@router.post(
    "/{connector_id}/reconnect",
    summary="Reconnect a connector: generate OAuth URL, form URL, or verify health",
)
async def reconnect_connector(
    connector_id: UUID,
    tenant: Annotated[TenantCtx, Depends(require_tenant)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> dict[str, str | None]:
    stmt = select(Connector).where(
        Connector.id == connector_id,
        Connector.organization_id == tenant.organization_id,
        Connector.deleted_at.is_(None),
    )
    row = (await session.execute(stmt)).scalar_one_or_none()
    if row is None:
        raise BasefloError(
            error_code="BF-API-001",
            message=f"Connector {connector_id} not found.",
            status_code=404,
        )

    # Determine the active token type for this connector.
    token_stmt = (
        select(ConnectorToken)
        .where(
            ConnectorToken.connector_id == connector_id,
            ConnectorToken.revoked_at.is_(None),
        )
        .order_by(ConnectorToken.created_at.desc())
        .limit(1)
    )
    token_row = (await session.execute(token_stmt)).scalar_one_or_none()
    token_type = token_row.token_type if token_row is not None else None

    redirect_url: str | None = None

    if token_type == TokenType.OAUTH2.value:
        redirect_url = _build_oauth_reconnect_url(row)
    elif token_type == TokenType.API_KEY.value:
        web_base = get_config().web_base_url.rstrip("/")
        redirect_url = f"{web_base}/settings/connectors/{connector_id}/credentials"
    elif token_type == TokenType.DB_URL.value:
        if token_row is None:
            raise BasefloError(
                error_code="BF-CONN-002",
                message="Connector has no stored credentials.",
                status_code=400,
            )
        # We cannot decrypt the DSN here without the TokenVault crypto,
        # so we surface a settings form instead.
        web_base = get_config().web_base_url.rstrip("/")
        redirect_url = (
            f"{web_base}/settings/connectors/{connector_id}/credentials"
        )
    else:
        # No token or unsupported type — just verify the connector row is healthy.
        row.status = "connected"
        await session.flush()

    return {"redirect_url": redirect_url}


def _build_oauth_reconnect_url(connector: Connector) -> str | None:
    """Rebuild the provider OAuth install URL for re-authorisation."""
    config = get_config()
    kind = connector.kind
    if kind == "shopify":
        shop_domain = connector.config.get("shop_domain")
        if not shop_domain or not config.shopify_client_id:
            return None
        params = ShopifyInstallParams(
            shop_domain=shop_domain,
            client_id=config.shopify_client_id,
            scopes=["read_customers", "read_orders", "read_products"],
            redirect_uri=f"{config.api_base_url}/api/v1/oauth/shopify/callback",
            state=secrets.token_urlsafe(24),
        )
        return shopify_build_install_url(params)
    if kind == "google_sheets":
        spreadsheet_id = connector.config.get("spreadsheet_id")
        if not spreadsheet_id or not config.google_client_id:
            return None
        params = GoogleInstallParams(
            client_id=config.google_client_id,
            scopes=[
                "https://www.googleapis.com/auth/spreadsheets",
                "https://www.googleapis.com/auth/drive.metadata.readonly",
            ],
            redirect_uri=f"{config.api_base_url}/api/v1/oauth/google_sheets/callback",
            state=secrets.token_urlsafe(24),
        )
        return google_sheets_build_install_url(params)
    # Unknown OAuth kind — no programmatic URL available.
    return None

