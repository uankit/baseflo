"""Integration tests for key API routes."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


class TestHealth:
    def test_health_liveness(self) -> None:
        response = client.get("/api/v1/health")
        assert response.status_code == 200
        assert response.json()["status"] == "ok"

    def test_health_readiness(self) -> None:
        response = client.get("/api/v1/health/ready")
        assert response.status_code == 200


class TestAuth:
    @pytest.mark.integration
    def test_magic_link_request_accepts_email(self) -> None:
        response = client.post(
            "/api/v1/auth/magic-link/request",
            json={"email": "test@example.com"},
        )
        # 202 even for unknown emails (security-through-obscurity)
        assert response.status_code == 202

    def test_me_without_session_returns_401(self) -> None:
        response = client.get("/api/v1/auth/me")
        assert response.status_code == 401


class TestConnectors:
    def test_list_connectors_without_auth_returns_401(self) -> None:
        response = client.get("/api/v1/connectors")
        assert response.status_code == 401
