"""FastAPI application entrypoint."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any, cast

import redis.asyncio as redis
import uvicorn
from fastapi import FastAPI
from redis.asyncio.client import Redis
from sqlalchemy import text

from app.core.config import settings
from app.db.session import AsyncSessionLocal, dispose_engine


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    """Manage application resources."""

    yield
    await dispose_engine()


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""

    app = FastAPI(
        title=settings.app_name,
        debug=settings.debug,
        version="0.1.0",
        lifespan=lifespan,
    )

    @app.get("/health", tags=["health"])
    async def healthcheck() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/ready", tags=["health"])
    async def readiness() -> dict[str, Any]:
        checks: dict[str, str] = {}

        async with AsyncSessionLocal() as session:
            await session.execute(text("SELECT 1"))
            checks["database"] = "ok"

        redis_client = cast(
            Redis,
            redis.from_url( 
                settings.redis_url,
                encoding="utf-8",
                decode_responses=True,
            ),
        )
        try:
            await redis_client.ping()
            checks["redis"] = "ok"
        finally:
            await redis_client.aclose()

        return {"status": "ok", "checks": checks}

    return app


app = create_app()


def main() -> None:
    """Run the API with Uvicorn."""

    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
