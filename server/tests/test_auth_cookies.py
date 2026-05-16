from __future__ import annotations

from fastapi import Response


def test_auth_cookies_are_scoped_for_rest_and_sse() -> None:
    from app.api.auth import _clear_auth_cookies, _set_auth_cookies

    response = Response()
    _set_auth_cookies(response, "access-token", "refresh-token")

    cookie_headers = [
        value.decode("latin1")
        for key, value in response.raw_headers
        if key.decode("latin1").lower() == "set-cookie"
    ]

    assert any(header.startswith("access_token=access-token;") and "Path=/" in header for header in cookie_headers)
    assert any(
        header.startswith("refresh_token=refresh-token;") and "Path=/api/v1/auth/token" in header
        for header in cookie_headers
    )

    clear_response = Response()
    _clear_auth_cookies(clear_response)
    clear_headers = [
        value.decode("latin1")
        for key, value in clear_response.raw_headers
        if key.decode("latin1").lower() == "set-cookie"
    ]
    assert any(header.startswith("access_token=") and "Path=/" in header for header in clear_headers)
    assert any(
        header.startswith("refresh_token=") and "Path=/api/v1/auth/token" in header
        for header in clear_headers
    )
