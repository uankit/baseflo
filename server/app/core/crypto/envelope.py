"""Envelope encryption: per-blob fresh DEK wrapped by KEK; AES-256-GCM cipher.

Per docs/40-features/SECURITY.md §3.3.
"""

from __future__ import annotations

import os

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from pydantic import BaseModel, ConfigDict

from app.core.crypto.kms import KMSClient
from app.core.errors import BasefloError

__all__ = ["EncryptedBlob", "EnvelopeCrypto"]


_NONCE_BYTES = 12


class EncryptedBlob(BaseModel):
    """An envelope-encrypted payload + the metadata needed to decrypt it.

    Persistence: callers split fields across columns. For `connector_tokens`
    the layout is `ciphertext`, `wrapped_dek`, `kek_alias`.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    ciphertext: bytes
    nonce: bytes
    wrapped_dek: bytes
    kek_alias: str


class EnvelopeCrypto:
    """Envelope-encryption helper bound to one KMS client + KEK alias.

    Why per-blob DEK rather than per-tenant: rotates implicitly on every
    write, limits blast radius if a single DEK ever leaks, matches Shopify /
    Stripe / AWS S3 conventions.
    """

    def __init__(self, *, kms: KMSClient, kek_alias: str) -> None:
        self._kms = kms
        self._kek_alias = kek_alias

    def encrypt(self, plaintext: bytes) -> EncryptedBlob:
        dek_plain, dek_wrapped = self._kms.generate_data_key(num_bytes=32)
        nonce = os.urandom(_NONCE_BYTES)
        ciphertext = AESGCM(dek_plain).encrypt(nonce, plaintext, associated_data=None)
        return EncryptedBlob(
            ciphertext=ciphertext,
            nonce=nonce,
            wrapped_dek=dek_wrapped,
            kek_alias=self._kek_alias,
        )

    def decrypt(self, blob: EncryptedBlob) -> bytes:
        dek_plain = self._kms.decrypt_data_key(blob.wrapped_dek)
        try:
            return AESGCM(dek_plain).decrypt(
                blob.nonce, blob.ciphertext, associated_data=None,
            )
        except InvalidTag as exc:
            raise BasefloError(
                error_code="BF-SEC-001",
                message="Envelope ciphertext failed authentication; data may be tampered.",
                status_code=500,
                cause=exc,
            ) from exc
