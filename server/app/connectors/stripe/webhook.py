"""Stripe webhook signature verification.

Per docs/40-features/CONN-STRIPE.md §7. Stripe sends each delivery with a
header of the form ``t=1700000000,v1=hex...,v1=hex...``. We parse the pairs,
compute HMAC-SHA256 over `f"{t}.{body.decode()}"` with the endpoint secret,
and accept iff the computed digest matches any `v1=` value AND the timestamp
is within tolerance.

Pure — caller supplies the current time so this is easy to unit-test with
frozen clocks.
"""

from __future__ import annotations

import hashlib
import hmac
from typing import Final

from app.core.errors import BasefloError


__all__ = [
    "DEFAULT_TOLERANCE_SECONDS",
    "SIGNATURE_HEADER",
    "require_valid_webhook",
    "verify_webhook",
]


SIGNATURE_HEADER: Final = "Stripe-Signature"
DEFAULT_TOLERANCE_SECONDS: Final = 300


def verify_webhook(
    *,
    raw_body: bytes,
    header_value: str | None,
    secret: str,
    now_unix: int,
    tolerance_seconds: int = DEFAULT_TOLERANCE_SECONDS,
) -> bool:
    """Return True iff `header_value` carries a valid v1 signature for
    `raw_body` under `secret`, and its timestamp is within `tolerance_seconds`
    of `now_unix`.

    Constant-time comparison; never raises on malformed input.
    """
    if not header_value or not secret:
        return False

    parsed = _parse_signature_header(header_value)
    if parsed is None:
        return False
    timestamp, signatures = parsed

    if abs(now_unix - timestamp) > tolerance_seconds:
        return False  # replay window exceeded

    signed_payload = f"{timestamp}.".encode("utf-8") + raw_body
    expected_hex = hmac.new(
        key=secret.encode("utf-8"),
        msg=signed_payload,
        digestmod=hashlib.sha256,
    ).hexdigest()

    for sig in signatures:
        if hmac.compare_digest(expected_hex, sig):
            return True
    return False


def require_valid_webhook(
    *,
    raw_body: bytes,
    header_value: str | None,
    secret: str,
    now_unix: int,
    tolerance_seconds: int = DEFAULT_TOLERANCE_SECONDS,
) -> None:
    """Raise `BF-CONN-STRIPE-002` if the signature doesn't match."""
    if not verify_webhook(
        raw_body=raw_body, header_value=header_value, secret=secret,
        now_unix=now_unix, tolerance_seconds=tolerance_seconds,
    ):
        raise BasefloError(
            error_code="BF-CONN-STRIPE-002",
            message="Stripe webhook signature verification failed.",
            status_code=401,
        )


def _parse_signature_header(header_value: str) -> tuple[int, list[str]] | None:
    """Parse `t=<unix>,v1=<hex>,v1=<hex>...`. Returns (t, [v1 sigs]) or None.

    Pairs without a recognised key are ignored; tolerant to any v0 / v2
    schemes Stripe might add later.
    """
    timestamp: int | None = None
    signatures: list[str] = []
    for pair in header_value.split(","):
        pair = pair.strip()
        if "=" not in pair:
            return None
        key, _, value = pair.partition("=")
        key = key.strip()
        value = value.strip()
        if key == "t":
            try:
                timestamp = int(value)
            except ValueError:
                return None
        elif key == "v1":
            signatures.append(value)

    if timestamp is None or not signatures:
        return None
    return timestamp, signatures
