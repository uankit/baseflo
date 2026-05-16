"""Generic OAuth lifecycle helpers for connector runtimes."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from typing import Any
from uuid import UUID

from connectors import AuthMethod, get_spec

from app.auth.service import encode_oauth_state
from app.connector_runtime.adapters import OAuthCallbackError, OAuthCredentialsResult
from app.connector_runtime.factory import get_source_instance, oauth_callback_url
from app.connector_runtime.registry import get_connector_runtime
from app.core.errors import NotFoundError, ValidationError


def build_authorize_url(
    *,
    kind: str,
    user_id: UUID,
    organization_id: UUID,
    payload: Mapping[str, Any],
) -> str:
    try:
        spec = get_spec(kind)
    except Exception as exc:
        raise NotFoundError(
            message=f"Unknown connector kind: {kind}",
            code="UNKNOWN_CONNECTOR",
            status_hint=404,
        ) from exc

    if spec.auth_method != AuthMethod.OAUTH2:
        raise ValidationError(
            message=f"Non-OAuth connectors not supported yet (auth_method={spec.auth_method.value})",
            code="AUTH_METHOD_UNSUPPORTED",
            status_hint=400,
        )

    runtime = get_connector_runtime(kind)
    source = get_source_instance(kind)
    plan = runtime.oauth_start_plan(
        source=source,
        payload=payload,
        redirect_uri=oauth_callback_url(kind),
    )
    state = encode_oauth_state(
        user_id=str(user_id),
        organization_id=str(organization_id),
        kind=kind,
        extra=plan.extra_state,
    )
    return source.authorize_url(state=state, **plan.authorize_kwargs)  # type: ignore[attr-defined]


async def credentials_from_callback(
    *,
    kind: str,
    query_params: Mapping[str, Any],
    state_payload: Mapping[str, Any],
    code: str,
    now: datetime,
) -> OAuthCredentialsResult:
    runtime = get_connector_runtime(kind)
    source = get_source_instance(kind)
    return await runtime.oauth_credentials_from_callback(
        source=source,
        query_params=query_params,
        state_payload=state_payload,
        code=code,
        redirect_uri=oauth_callback_url(kind),
        now=now,
    )


__all__ = [
    "OAuthCallbackError",
    "build_authorize_url",
    "credentials_from_callback",
]
