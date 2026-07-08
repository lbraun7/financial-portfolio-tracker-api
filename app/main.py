"""FastAPI application entrypoint."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any, cast

import redis.asyncio as redis
import uvicorn
from fastapi import FastAPI
from redis.asyncio.client import Redis
from sqlalchemy import text

from app.api.v1.assets import router as assets_router
from app.api.v1.auth import router as auth_router
from app.api.v1.portfolios import router as portfolios_router
from app.api.v1.positions import router as positions_router
from app.api.v1.transactions import router as transactions_router
from app.core.config import settings
from app.core.logging import RequestLoggingMiddleware, configure_logging
from app.db.session import AsyncSessionLocal, dispose_engine


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    """Manage application resources."""

    yield
    await dispose_engine()


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""

    configure_logging()
    app = FastAPI(
        title=settings.app_name,
        debug=settings.debug,
        version="0.1.0",
        lifespan=lifespan,
    )
    app.add_middleware(RequestLoggingMiddleware)

    @app.get("/health", tags=["health"])
    async def healthcheck() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/ready", tags=["health"])
    async def readiness() -> dict[str, Any]:
        checks: dict[str, str] = {}

        async with AsyncSessionLocal() as session:
            await session.execute(text("SELECT 1"))
            checks["database"] = "ok"

        redis_from_url = cast(Any, redis.from_url)
        redis_client = cast(
            Redis,
            redis_from_url(settings.redis_url, encoding="utf-8", decode_responses=True),
        )
        try:
            await redis_client.ping()
            checks["redis"] = "ok"
        finally:
            await redis_client.aclose()

        return {"status": "ok", "checks": checks}

    app.include_router(auth_router, prefix=settings.api_v1_prefix)
    app.include_router(assets_router, prefix=settings.api_v1_prefix)
    app.include_router(portfolios_router, prefix=settings.api_v1_prefix)
    app.include_router(transactions_router, prefix=settings.api_v1_prefix)
    app.include_router(positions_router, prefix=settings.api_v1_prefix)

    return app


app = create_app()


def main() -> None:
    """Run the API with Uvicorn."""

    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
