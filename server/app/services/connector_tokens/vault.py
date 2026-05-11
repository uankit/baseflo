"""TokenVault — envelope-encrypted connector token storage.

Per docs/40-features/SECURITY.md §3.3. The connector_tokens row stores:

  - `ciphertext`   — `nonce(12) || aead_ciphertext`. Outer AES-GCM encryption
                      under a per-blob DEK.
  - `wrapped_dek`  — DEK wrapped by the KEK; decrypts via the KMSClient.
  - `expires_at`   — provider-side expiry (None for non-expiring tokens).
  - `scopes`       — granted OAuth scopes.

Plaintext is JSON-encoded `{access_token: ..., refresh_token?: ..., ...}` —
the connector framework reads keys from the dict it knows about.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Protocol
from uuid import UUID

from app.core.crypto.envelope import EncryptedBlob, EnvelopeCrypto
from app.core.errors import BasefloError

__all__ = ["StoredToken", "TokenVault", "TokenVaultRepository"]


_NONCE_BYTES = 12


@dataclass(frozen=True, slots=True)
class StoredToken:
    """Decrypted connector token, ready for use by the connector adapter."""

    token_id: UUID
    payload: dict[str, Any]
    expires_at: datetime | None
    scopes: list[str]


class TokenVaultRepository(Protocol):
    async def put(
        self,
        *,
        connector_id: UUID,
        token_type: str,
        ciphertext: bytes,
        wrapped_dek: bytes,
        expires_at: datetime | None,
        scopes: list[str],
    ) -> UUID: ...

    async def find_active(
        self, connector_id: UUID,
    ) -> tuple[UUID, bytes, bytes, datetime | None, list[str]] | None: ...

    async def revoke(self, token_id: UUID, revoked_at: datetime) -> None: ...


class TokenVault:
    """Encrypts on `put`, decrypts on `get`. Stateless apart from its deps."""

    def __init__(
        self,
        *,
        repo: TokenVaultRepository,
        crypto: EnvelopeCrypto,
    ) -> None:
        self._repo = repo
        self._crypto = crypto

    async def put(
        self,
        *,
        connector_id: UUID,
        token_type: str,
        payload: dict[str, Any],
        expires_at: datetime | None = None,
        scopes: list[str] | None = None,
    ) -> UUID:
        plaintext = json.dumps(payload, sort_keys=True).encode("utf-8")
        blob = self._crypto.encrypt(plaintext)
        packed = blob.nonce + blob.ciphertext
        return await self._repo.put(
            connector_id=connector_id,
            token_type=token_type,
            ciphertext=packed,
            wrapped_dek=blob.wrapped_dek,
            expires_at=expires_at,
            scopes=scopes or [],
        )

    async def get(self, connector_id: UUID) -> StoredToken | None:
        record = await self._repo.find_active(connector_id)
        if record is None:
            return None
        token_id, packed, wrapped_dek, expires_at, scopes = record
        if len(packed) < _NONCE_BYTES + 1:
            raise BasefloError(
                error_code="BF-SEC-001",
                message="Connector token ciphertext is shorter than nonce.",
                status_code=500,
            )
        nonce, ciphertext = packed[:_NONCE_BYTES], packed[_NONCE_BYTES:]
        blob = EncryptedBlob(
            ciphertext=ciphertext,
            nonce=nonce,
            wrapped_dek=wrapped_dek,
            kek_alias="local-default",
        )
        plaintext = self._crypto.decrypt(blob)
        try:
            payload = json.loads(plaintext)
        except ValueError as exc:
            raise BasefloError(
                error_code="BF-SEC-001",
                message="Connector token plaintext is not valid JSON.",
                status_code=500,
                cause=exc,
            ) from exc
        if not isinstance(payload, dict):
            raise BasefloError(
                error_code="BF-SEC-001",
                message="Connector token plaintext is not a JSON object.",
                status_code=500,
            )
        return StoredToken(
            token_id=token_id,
            payload=payload,
            expires_at=expires_at,
            scopes=scopes,
        )

    async def revoke(self, token_id: UUID) -> None:
        await self._repo.revoke(token_id, datetime.now(UTC))
