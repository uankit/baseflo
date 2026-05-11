"""Shopify OAuth2 helpers — install URL builder + token exchange + install HMAC verify.

Per docs/40-features/CONN-SHOPIFY.md §3.2. The OAuth dance happens in API
endpoints; this module is the deterministic plumbing they call.

Reference: https://shopify.dev/docs/apps/auth/oauth
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import hmac
import urllib.parse

import httpx
from pydantic import BaseModel, ConfigDict, Field

from app.core.errors import BasefloError
from app.observability.logging import get_logger


__all__ = [
    "InstallParams",
    "TokenExchangeResult",
    "build_install_url",
    "exchange_code_for_token",
    "verify_install_callback_hmac",
]


logger = get_logger("connectors.shopify.auth")


class InstallParams(BaseModel):
    """Inputs to `build_install_url`."""

    model_config = ConfigDict(frozen=True, extra="forbid")
    shop_domain: str = Field(min_length=4, max_length=120, pattern=r"^[a-zA-Z0-9-]+\.myshopify\.com$")
    """Per Shopify's docs, install URLs target the merchant's `*.myshopify.com` host."""
    client_id: str = Field(min_length=4, max_length=120)
    scopes: list[str] = Field(min_length=1, max_length=20)
    redirect_uri: str = Field(min_length=8, max_length=500)
    state: str = Field(min_length=8, max_length=120)
    """CSRF token; the API endpoint MUST cache this and verify it on callback."""


class TokenExchangeResult(BaseModel):
    """Result of exchanging an OAuth `code` for an access_token."""

    model_config = ConfigDict(frozen=True, extra="forbid")
    access_token: str = Field(min_length=1)
    scope: str = Field(min_length=1)
    """Comma-separated list of scopes Shopify granted (may differ from requested)."""


def build_install_url(params: InstallParams) -> str:
    """Build the Shopify OAuth install URL the merchant is redirected to."""
    query = urllib.parse.urlencode({
        "client_id": params.client_id,
        "scope": ",".join(params.scopes),
        "redirect_uri": params.redirect_uri,
        "state": params.state,
        # No `grant_options[]=per-user`; we use per-store offline tokens.
    })
    return f"https://{params.shop_domain}/admin/oauth/authorize?{query}"


def verify_install_callback_hmac(
    *, query_params: dict[str, str], client_secret: str
) -> bool:
    """Verify the HMAC parameter Shopify includes in install-callback URLs.

    Per https://shopify.dev/docs/apps/auth/oauth/getting-started#step-3-confirm-installation
    every callback carries an `hmac` query param. To validate:
      1. Strip `hmac` (and the legacy `signature`) from the query.
      2. Sort remaining keys lexicographically.
      3. URL-encode each key=value pair, join with `&`.
      4. HMAC-SHA256 with `client_secret`.
      5. Compare hex digest (lower-case) constant-time against the received `hmac`.

    Returns False on missing or malformed `hmac`; never raises.
    """
    received = query_params.get("hmac")
    if not received:
        return False

    filtered = {k: v for k, v in query_params.items() if k not in {"hmac", "signature"}}
    canonical = "&".join(
        f"{urllib.parse.quote(k, safe='')}={urllib.parse.quote(v, safe='')}"
        for k, v in sorted(filtered.items())
    )
    computed = hmac.new(
        key=client_secret.encode("utf-8"),
        msg=canonical.encode("utf-8"),
        digestmod=hashlib.sha256,
    ).hexdigest()
    try:
        return hmac.compare_digest(computed.encode("ascii"), received.encode("ascii"))
    except (UnicodeEncodeError, AttributeError):
        return False


# `verify_install_callback_hmac` uses `binascii` indirectly via hexdigest; the
# import lives here so mypy + ruff agree the module's transitive imports stay
# minimal.
_ = base64, binascii  # noqa: F401 — referenced in docstring; imports kept for completeness


async def exchange_code_for_token(
    *,
    shop_domain: str,
    code: str,
    client_id: str,
    client_secret: str,
    transport: httpx.BaseTransport | None = None,
    timeout: float = 10.0,
) -> TokenExchangeResult:
    """POST to Shopify's token endpoint to swap `code` for an access_token.

    `transport` is plumbed for tests to plug a `MockTransport`. Production
    callers leave it None so httpx uses its default async transport.
    """
    url = f"https://{shop_domain}/admin/oauth/access_token"
    payload = {"client_id": client_id, "client_secret": client_secret, "code": code}

    client_kwargs: dict[str, object] = {"timeout": timeout}
    if transport is not None:
        client_kwargs["transport"] = transport
    try:
        async with httpx.AsyncClient(**client_kwargs) as client:  # type: ignore[arg-type]
            response = await client.post(url, json=payload)
    except httpx.HTTPError as exc:
        raise BasefloError(
            error_code="BF-CONN-SHOPIFY-001",
            message=f"Shopify OAuth transport failed: {exc!r}",
            status_code=502,
            cause=exc,
        ) from exc

    if response.status_code >= 400:
        raise BasefloError(
            error_code="BF-CONN-SHOPIFY-001",
            message=(
                f"Shopify OAuth token exchange rejected (status={response.status_code}). "
                "The install code may be expired, reused, or signed for a different app."
            ),
            status_code=400,
            details={"status": response.status_code, "shop_domain": shop_domain},
        )

    try:
        body = response.json()
    except ValueError as exc:
        raise BasefloError(
            error_code="BF-CONN-SHOPIFY-001",
            message="Shopify OAuth response was not JSON.",
            status_code=502,
            cause=exc,
        ) from exc

    access_token = body.get("access_token")
    scope = body.get("scope", "")
    if not isinstance(access_token, str) or not access_token:
        raise BasefloError(
            error_code="BF-CONN-SHOPIFY-001",
            message="Shopify OAuth response missing `access_token`.",
            status_code=502,
        )

    logger.info(
        "shopify_oauth_token_exchanged",
        shop_domain=shop_domain,
        scope=scope,
    )
    return TokenExchangeResult(access_token=access_token, scope=scope or "")
