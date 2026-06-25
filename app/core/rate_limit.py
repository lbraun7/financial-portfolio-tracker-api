"""Redis-backed fixed-window request rate limiting."""

from __future__ import annotations

from typing import Annotated, Any, cast

import redis.asyncio as redis
from fastapi import Depends, HTTPException, Request, status
from redis.asyncio.client import Redis
from redis.exceptions import RedisError

from app.core.config import settings


class RateLimiter:
    """Apply an atomic fixed-window limit using Redis counters."""

    async def check(self, *, key: str, limit: int, window_seconds: int) -> int:
        """Increment a counter and return the number of requests remaining."""

        redis_from_url = cast(Any, redis.from_url)
        client = cast(
            Redis,
            redis_from_url(settings.redis_url, encoding="utf-8", decode_responses=True),
        )
        try:
            async with client.pipeline(transaction=True) as pipeline:
                pipeline.incr(key)
                pipeline.ttl(key)
                current, ttl = await pipeline.execute()
            current_count = int(current)
            current_ttl = int(ttl)
            if current_count == 1 or current_ttl < 0:
                await client.expire(key, window_seconds)
            return limit - current_count
        finally:
            await client.aclose()


def get_rate_limiter() -> RateLimiter:
    """Return the application rate limiter."""

    return RateLimiter()


async def enforce_auth_rate_limit(
    request: Request,
    limiter: Annotated[RateLimiter, Depends(get_rate_limiter)],
) -> None:
    """Limit authentication attempts by client IP and endpoint."""

    if not settings.rate_limit_enabled:
        return

    client_ip = request.client.host if request.client else "unknown"
    key = f"rate-limit:auth:{request.url.path}:{client_ip}"
    try:
        remaining = await limiter.check(
            key=key,
            limit=settings.rate_limit_auth_requests,
            window_seconds=settings.rate_limit_auth_window_seconds,
        )
    except (RedisError, ConnectionError, OSError) as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Rate limiting service is unavailable",
        ) from exc

    if remaining < 0:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many requests",
            headers={"Retry-After": str(settings.rate_limit_auth_window_seconds)},
        )
