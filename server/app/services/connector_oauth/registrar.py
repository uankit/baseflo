"""ConnectorRegistrar — atomic Connector + encrypted token persistence.

After a connector OAuth callback runs, the route calls
`registrar.register(ConnectorRegistration(...))`. The registrar inserts the
`Connector` row, then puts the token through `TokenVault` so the row in
`connector_tokens` is envelope-encrypted at rest.

Both writes share the same SQLAlchemy session, so they commit together.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING, Any
from uuid import UUID

from app.db.models.connector import Connector, ConnectorStatus

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.services.connector_tokens.vault import TokenVault


__all__ = ["ConnectorRegistrar", "ConnectorRegistration"]


@dataclass(frozen=True, slots=True)
class ConnectorRegistration:
    """Everything the registrar needs to persist one connector handshake."""

    organization_id: UUID
    project_id: UUID
    kind: str
    display_name: str
    config: dict[str, Any]
    token_type: str
    token_payload: dict[str, Any]
    token_scopes: list[str]
    token_expires_at: datetime | None = None


class ConnectorRegistrar:
    def __init__(self, *, session: AsyncSession, vault: TokenVault) -> None:
        self._session = session
        self._vault = vault

    async def register(self, registration: ConnectorRegistration) -> UUID:
        connector = Connector(
            organization_id=registration.organization_id,
            project_id=registration.project_id,
            kind=registration.kind,
            display_name=registration.display_name,
            config=registration.config,
            status=ConnectorStatus.CONNECTED.value,
        )
        self._session.add(connector)
        await self._session.flush()

        await self._vault.put(
            connector_id=connector.id,
            token_type=registration.token_type,
            payload=registration.token_payload,
            expires_at=registration.token_expires_at,
            scopes=registration.token_scopes,
        )
        return connector.id
