"""Pytest configuration and shared fixtures."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator
from typing import Any
from unittest.mock import AsyncMock

import pytest

pytest_plugins = ("pytest_asyncio",)


@pytest.fixture(scope="session")
def event_loop() -> asyncio.AbstractEventLoop:
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
async def mock_session() -> AsyncGenerator[AsyncMock, None]:
    """Mock SQLAlchemy async session for unit tests."""
    session = AsyncMock()
    yield session
