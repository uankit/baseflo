"""HMAC-SHA256 webhook verification.

Per docs/40-features/CONN-SHOPIFY.md §3.6 + Shopify's documented signing
scheme: every webhook delivery includes an `X-Shopify-Hmac-Sha256` header
whose value is the base64-encoded HMAC-SHA256 of the raw request body using
the app's shared secret.

The function is pure (no I/O, no env reads) so the call site is responsible
for supplying the secret. Mismatch → `BF-CONN-SHOPIFY-002`.
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import hmac

from app.core.errors import BasefloError


__all__ = ["HMAC_HEADER", "verify_webhook"]


HMAC_HEADER = "X-Shopify-Hmac-Sha256"
"""Canonical header name. Lookup must be case-insensitive at the call site
(HTTP headers are; FastAPI exposes them via case-insensitive Mapping)."""


def verify_webhook(*, raw_body: bytes, header_value: str | None, secret: str) -> bool:
    """Return True iff `header_value` is the correct HMAC-SHA256 of `raw_body`.

    Args:
        raw_body: the raw request body bytes Shopify sent. Must be the exact
            bytes — re-serialising the JSON before hashing produces a different
            digest and rejects the request.
        header_value: the value of `X-Shopify-Hmac-Sha256`, base64-encoded.
            None / empty / non-base64 → False (no exception leaks to caller
            to discourage signature-oracle timing attacks).
        secret: the app's shared secret. Caller reads it from app config
            (`BASEFLO_SHOPIFY_CLIENT_SECRET`) and passes it in.

    Constant-time comparison via `hmac.compare_digest` so timing of valid
    vs. invalid signatures does not leak the prefix.
    """
    if not header_value or not secret:
        return False
    try:
        received = base64.b64decode(header_value, validate=True)
    except (binascii.Error, ValueError):
        return False
    expected = hmac.new(
        key=secret.encode("utf-8"),
        msg=raw_body,
        digestmod=hashlib.sha256,
    ).digest()
    return hmac.compare_digest(received, expected)


def require_valid_webhook(
    *, raw_body: bytes, header_value: str | None, secret: str
) -> None:
    """Raise `BF-CONN-SHOPIFY-002` if the signature doesn't match.

    Convenience wrapper for the API endpoint; keeps the typed-error path
    consistent across all webhook ingestion routes.
    """
    if not verify_webhook(raw_body=raw_body, header_value=header_value, secret=secret):
        raise BasefloError(
            error_code="BF-CONN-SHOPIFY-002",
            message="Shopify webhook HMAC verification failed.",
            status_code=401,
        )
