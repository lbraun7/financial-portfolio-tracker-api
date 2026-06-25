"""Rate limiting tests."""

from __future__ import annotations

from typing import Any

import pytest
from app.core.config import settings
from app.core.rate_limit import RateLimiter, enforce_auth_rate_limit
from fastapi import HTTPException
from pytest import MonkeyPatch
from starlette.requests import Request


def make_request(path: str = "/api/v1/auth/login") -> Request:
    scope: dict[str, Any] = {
        "type": "http",
        "method": "POST",
        "path": path,
        "raw_path": path.encode(),
        "query_string": b"",
        "headers": [],
        "client": ("127.0.0.1", 1234),
        "server": ("testserver", 80),
        "scheme": "http",
    }
    return Request(scope)


@pytest.mark.asyncio
async def test_auth_rate_limit_is_skipped_when_disabled(monkeypatch: MonkeyPatch) -> None:
    class StubLimiter:
        async def check(self, **_kwargs: object) -> int:
            raise AssertionError("limiter should not be called")

    monkeypatch.setattr(settings, "rate_limit_enabled", False)

    await enforce_auth_rate_limit(make_request(), StubLimiter())  # type: ignore[arg-type]


@pytest.mark.asyncio
async def test_auth_rate_limit_rejects_exhausted_window(monkeypatch: MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    class StubLimiter:
        async def check(self, **kwargs: object) -> int:
            captured.update(kwargs)
            return -1

    monkeypatch.setattr(settings, "rate_limit_enabled", True)
    monkeypatch.setattr(settings, "rate_limit_auth_requests", 5)
    monkeypatch.setattr(settings, "rate_limit_auth_window_seconds", 60)

    with pytest.raises(HTTPException) as exc_info:
        await enforce_auth_rate_limit(make_request(), StubLimiter())  # type: ignore[arg-type]

    assert exc_info.value.status_code == 429
    assert exc_info.value.headers == {"Retry-After": "60"}
    assert captured["limit"] == 5
    assert captured["window_seconds"] == 60
    assert captured["key"] == "rate-limit:auth:/api/v1/auth/login:127.0.0.1"


@pytest.mark.asyncio
async def test_auth_rate_limit_allows_requests_with_remaining_capacity(
    monkeypatch: MonkeyPatch,
) -> None:
    class StubLimiter(RateLimiter):
        async def check(self, *, key: str, limit: int, window_seconds: int) -> int:
            return 3

    monkeypatch.setattr(settings, "rate_limit_enabled", True)

    await enforce_auth_rate_limit(make_request(), StubLimiter())
