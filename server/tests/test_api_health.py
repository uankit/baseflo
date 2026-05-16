from __future__ import annotations

from typing import Any

import pytest


class _HealthyConnection:
    async def __aenter__(self) -> _HealthyConnection:
        return self

    async def __aexit__(self, *_args: object) -> None:
        return None

    async def execute(self, _statement: object) -> None:
        return None


class _HealthyEngine:
    def connect(self) -> _HealthyConnection:
        return _HealthyConnection()


class _BrokenEngine:
    def connect(self) -> Any:
        raise RuntimeError("database unavailable")


@pytest.mark.asyncio
async def test_health_endpoint_reports_database_ok(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.api.health import health_endpoint

    monkeypatch.setattr("app.api.health.engine", _HealthyEngine())

    response = await health_endpoint()

    assert response["ok"] is True
    assert response["healthy"] is True
    assert response["checks"]["database"] == {"ok": True}


@pytest.mark.asyncio
async def test_health_endpoint_reports_database_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.api.health import health_endpoint

    monkeypatch.setattr("app.api.health.engine", _BrokenEngine())

    response = await health_endpoint()

    assert response["ok"] is False
    assert response["healthy"] is False
    assert response["checks"]["database"]["ok"] is False
