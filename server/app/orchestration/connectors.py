"""Connector loader for saga-time use.

Per docs/40-features/CONN-FRAMEWORK.md §3.3 + docs/01-architecture.md §3.4.

Reads `connectors` rows for a project, decrypts the token via `TokenVault`,
instantiates the corresponding `Connector` class via the registry, and
yields typed `LoadedConnector` tuples ready for use by the agent saga,
backfill runner, and webhook reconciler.

The token's `metadata` is the merged shape of:
  - `connectors.config` (non-secret connection info: shop_domain, api_version,
    spreadsheet_id, etc.).
  - `connector_tokens.ciphertext` (envelope-decrypted secret payload:
    access_token, refresh_token, api_key, etc.).
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.connectors.base import Connector, ConnectorToken
from app.connectors.registry import ConnectorRegistry
from app.core.crypto.envelope import EnvelopeCrypto
from app.core.crypto.kms import get_kms_client
from app.db.models.connector import Connector as ConnectorRow
from app.db.models.connector import ConnectorStatus
from app.observability.logging import get_logger
from app.repositories.connector_tokens import ConnectorTokenRepository
from app.services.connector_tokens.vault import TokenVault

logger = get_logger("orchestration.connectors")


@dataclass(frozen=True, slots=True)
class LoadedConnector:
    """A live connector instance + its decrypted token, ready for use."""

    instance: Connector
    token: ConnectorToken
    row_id: UUID
    """Primary key of the persisted `connectors` row, for trace propagation."""
    config: dict[str, object]
    """Non-secret connection info (mirror of `connectors.config`)."""


async def load_active_connectors(
    session: AsyncSession,
    *,
    project_id: UUID,
) -> list[LoadedConnector]:
    """Return every active connector configured for the project.

    Inactive (revoked/error) connectors are filtered out — the saga doesn't
    try to introspect dead connections.
    """
    stmt = (
        select(ConnectorRow)
        .where(ConnectorRow.project_id == project_id)
        .where(ConnectorRow.deleted_at.is_(None))
        .where(ConnectorRow.status == ConnectorStatus.CONNECTED.value)
        .order_by(ConnectorRow.created_at)
    )
    rows = list((await session.execute(stmt)).scalars().all())

    vault = _build_vault(session)
    loaded: list[LoadedConnector] = []
    for row in rows:
        try:
            connector_cls = ConnectorRegistry.get(row.kind)
        except Exception as exc:  # noqa: BLE001 — typed error logged
            logger.warning(
                "connector_kind_not_registered",
                project_id=str(project_id), connector_id=str(row.id),
                kind=row.kind, exc=str(exc),
            )
            continue

        try:
            stored = await vault.get(row.id)
        except Exception as exc:  # noqa: BLE001 — decryption failure logged
            logger.warning(
                "connector_token_decrypt_failed",
                project_id=str(project_id), connector_id=str(row.id),
                kind=row.kind, exc=str(exc),
            )
            continue
        if stored is None:
            logger.warning(
                "connector_has_no_active_token",
                project_id=str(project_id), connector_id=str(row.id),
            )
            continue

        # Merge: parent config (non-secret) + decrypted token payload (secret).
        # Token payload wins on key collisions so per-token rotation takes effect.
        metadata: dict[str, object] = {**dict(row.config), **stored.payload}
        if stored.expires_at is not None:
            metadata.setdefault("expires_at", stored.expires_at.isoformat())

        loaded.append(LoadedConnector(
            instance=connector_cls(),
            token=ConnectorToken(
                connector_name=row.kind,
                token_id=stored.token_id,
                metadata=metadata,
            ),
            row_id=row.id,
            config=dict(row.config),
        ))

    return loaded


def _build_vault(session: AsyncSession) -> TokenVault:
    return TokenVault(
        repo=ConnectorTokenRepository(session),
        crypto=EnvelopeCrypto(kms=get_kms_client(), kek_alias="local-default"),
    )
