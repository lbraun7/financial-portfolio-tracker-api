"""Structured logging configuration and HTTP request instrumentation."""

from __future__ import annotations

import logging
import sys
import time
import uuid
from collections.abc import Awaitable, Callable
from typing import Any

import structlog
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.config import settings


def configure_logging() -> None:
    """Configure stdlib and structlog output for the current environment."""

    shared_processors: list[Any] = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        structlog.processors.StackInfoRenderer(),
    ]
    renderer: Any
    if settings.log_json:
        renderer = structlog.processors.JSONRenderer()
    else:
        renderer = structlog.dev.ConsoleRenderer(colors=False)

    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=settings.log_level.upper(),
        force=True,
    )
    structlog.configure(
        processors=[
            *shared_processors,
            structlog.processors.format_exc_info,
            renderer,
        ],
        wrapper_class=structlog.make_filtering_bound_logger(
            logging.getLevelNamesMapping().get(settings.log_level.upper(), logging.INFO)
        ),
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Attach a request ID and emit one structured event per HTTP response."""

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(request_id=request_id)
        started_at = time.perf_counter()
        logger = structlog.get_logger()

        try:
            response = await call_next(request)
        except Exception:
            logger.exception(
                "http_request_failed",
                method=request.method,
                path=request.url.path,
                duration_ms=round((time.perf_counter() - started_at) * 1000, 2),
            )
            raise

        response.headers["X-Request-ID"] = request_id
        logger.info(
            "http_request_completed",
            method=request.method,
            path=request.url.path,
            status_code=response.status_code,
            duration_ms=round((time.perf_counter() - started_at) * 1000, 2),
            client_ip=request.client.host if request.client else None,
        )
        structlog.contextvars.clear_contextvars()
        return response
