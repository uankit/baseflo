"""KMS strategy interface + LocalKMS implementation.

Per docs/40-features/SECURITY.md §3.3: envelope encryption wraps a per-blob
DEK with a KEK held in the KMS. `LocalKMSClient` is the default for local
development and self-host deployments where a single key in env is acceptable.
"""

from __future__ import annotations

import base64
import binascii
import os
from functools import lru_cache
from typing import Protocol, runtime_checkable

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from app.core.config import KMSProvider, get_config
from app.core.errors import BasefloError

__all__ = [
    "KMSClient",
    "LocalKMSClient",
    "get_kms_client",
]

_NONCE_BYTES = 12
"""AES-GCM canonical nonce length."""


@runtime_checkable
class KMSClient(Protocol):
    """Strategy: a KMS that can mint and unwrap data-encryption keys.

    `generate_data_key` returns `(plaintext_dek, wrapped_dek)`. The plaintext
    is held in process memory only long enough to encrypt one blob; only the
    wrapped form is persisted.
    """

    def generate_data_key(self, *, num_bytes: int = 32) -> tuple[bytes, bytes]: ...

    def decrypt_data_key(self, wrapped_dek: bytes) -> bytes: ...


# ---------- LocalKMSClient ----------


class LocalKMSClient:
    """AES-256-GCM KEK held in process memory.

    Wire format of `wrapped_dek`: ``nonce(12 bytes) || ciphertext+tag``.
    Suitable for local / self-host.
    """

    def __init__(self, *, kek: bytes) -> None:
        if len(kek) != 32:
            raise BasefloError(
                error_code="BF-SEC-001",
                message="LocalKMSClient KEK must be exactly 32 bytes (AES-256).",
                status_code=500,
            )
        self._aead = AESGCM(kek)

    @classmethod
    def from_base64(cls, encoded: str) -> LocalKMSClient:
        try:
            decoded = base64.b64decode(encoded, validate=True)
        except (ValueError, binascii.Error) as exc:
            raise BasefloError(
                error_code="BF-SEC-001",
                message="LocalKMSClient KEK is not valid base64.",
                status_code=500,
                cause=exc,
            ) from exc
        return cls(kek=decoded)

    def generate_data_key(self, *, num_bytes: int = 32) -> tuple[bytes, bytes]:
        plaintext = os.urandom(num_bytes)
        nonce = os.urandom(_NONCE_BYTES)
        wrapped = nonce + self._aead.encrypt(nonce, plaintext, associated_data=None)
        return plaintext, wrapped

    def decrypt_data_key(self, wrapped_dek: bytes) -> bytes:
        if len(wrapped_dek) < _NONCE_BYTES + 1:
            raise BasefloError(
                error_code="BF-SEC-001",
                message="Wrapped DEK is shorter than the minimum AES-GCM frame.",
                status_code=500,
            )
        nonce, ciphertext = wrapped_dek[:_NONCE_BYTES], wrapped_dek[_NONCE_BYTES:]
        try:
            return self._aead.decrypt(nonce, ciphertext, associated_data=None)
        except InvalidTag as exc:
            raise BasefloError(
                error_code="BF-SEC-001",
                message=(
                    "Wrapped DEK failed authentication; "
                    "key mismatch or tampered ciphertext."
                ),
                status_code=500,
                cause=exc,
            ) from exc


# ---------- factory ----------


@lru_cache(maxsize=1)
def get_kms_client() -> KMSClient:
    """Resolve the configured KMS client strategy.

    `BASEFLO_KMS_PROVIDER=local` requires `BASEFLO_LOCAL_KEK_BASE64` (32 bytes
    base64-encoded). AWS KMS is not available in v1; use LocalKMS.
    """
    config = get_config()
    if config.kms_provider == KMSProvider.LOCAL:
        local_kek = (
            config.local_kek_base64.get_secret_value().strip()
            if config.local_kek_base64 is not None
            else ""
        )
        if not local_kek:
            raise BasefloError(
                error_code="BF-SEC-006",
                message=(
                    "BASEFLO_KMS_PROVIDER=local but BASEFLO_LOCAL_KEK_BASE64 is unset."
                ),
                status_code=500,
            )
        return LocalKMSClient.from_base64(local_kek)
    if config.kms_provider == KMSProvider.AWS_KMS:
        raise BasefloError(
            error_code="BF-SEC-006",
            message="AWS KMS is not available in v1. Use LocalKMS.",
            status_code=500,
        )
    raise BasefloError(
        error_code="BF-SEC-006",
        message=f"Unknown KMS provider: {config.kms_provider!r}",
        status_code=500,
    )
