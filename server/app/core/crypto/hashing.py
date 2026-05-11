"""Password + high-entropy-token hashing primitives.

- `argon2id` for passwords: low-entropy human secrets, brute-force resistance.
- `sha-256` for high-entropy tokens (256-bit random session ids, magic-link
  tokens, API-key secrets) where speed matters and brute-force is infeasible
  by construction.
"""

from __future__ import annotations

import hashlib
import secrets

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

__all__ = [
    "generate_token_urlsafe",
    "hash_high_entropy_token",
    "hash_password",
    "verify_password",
]


_password_hasher = PasswordHasher()


def hash_password(plaintext: str) -> str:
    """Argon2id-encoded password hash. Includes salt + parameters."""
    return _password_hasher.hash(plaintext)


def verify_password(*, hashed: str, plaintext: str) -> bool:
    """Constant-time verify; returns False on mismatch or malformed hash."""
    try:
        return _password_hasher.verify(hashed, plaintext)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


def hash_high_entropy_token(plaintext: str) -> bytes:
    """SHA-256 raw 32-byte digest. Tokens must already be high-entropy.

    Lookup pattern: server stores `sha256(raw_token)`; client presents
    `raw_token` over TLS; server hashes and PK-looks-up. No brute force concern
    given >= 128 bits entropy in `raw_token`.
    """
    return hashlib.sha256(plaintext.encode("utf-8")).digest()


def generate_token_urlsafe(num_bytes: int = 32) -> str:
    """URL-safe random token (>= 256 bits entropy at default size)."""
    return secrets.token_urlsafe(num_bytes)
