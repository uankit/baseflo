"""Crypto primitives: KMS strategy, envelope encryption, hashing helpers.

Per docs/40-features/SECURITY.md §3.
"""

from app.core.crypto.envelope import EncryptedBlob, EnvelopeCrypto
from app.core.crypto.hashing import (
    generate_token_urlsafe,
    hash_high_entropy_token,
    hash_password,
    verify_password,
)
from app.core.crypto.kms import KMSClient, LocalKMSClient, get_kms_client

__all__ = [
    "EncryptedBlob",
    "EnvelopeCrypto",
    "KMSClient",
    "LocalKMSClient",
    "generate_token_urlsafe",
    "get_kms_client",
    "hash_high_entropy_token",
    "hash_password",
    "verify_password",
]
