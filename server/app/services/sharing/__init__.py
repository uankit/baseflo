"""Read-only share-link generation.

Per docs/30-features.md SEC-EXPORT (sharing). The token model is intentionally
a random 32-byte token with TTL stored in the existing `share_links` table.
"""

from __future__ import annotations

from app.services.sharing.tokens import (
    ShareLinkResult,
    create_share_link,
    revoke_share_link,
    verify_share_token,
)

__all__ = [
    "ShareLinkResult",
    "create_share_link",
    "revoke_share_link",
    "verify_share_token",
]
