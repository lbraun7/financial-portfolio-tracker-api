"""Market price fetching and caching service."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Protocol

from redis.exceptions import RedisError

from app.domain.money import quantize_price
from app.integrations.prices.base import PriceProvider


class PriceCache(Protocol):
    """Minimal async cache operations used by the pricing service."""

    async def get(self, key: str) -> str | bytes | None:
        """Return a cached value."""

    async def set(self, key: str, value: str, *, ex: int) -> object:
        """Store a value with an expiry."""


class PriceService:
    """Return provider prices while treating cache failures as cache misses."""

    CACHE_KEY_PREFIX = "market-price"

    def __init__(
        self,
        *,
        provider: PriceProvider,
        cache: PriceCache,
        ttl_seconds: int,
    ) -> None:
        self.provider = provider
        self.cache = cache
        self.ttl_seconds = ttl_seconds

    async def get_price(self, symbol: str) -> Decimal:
        normalized_symbol = symbol.strip().upper()
        cache_key = f"{self.CACHE_KEY_PREFIX}:{normalized_symbol}"
        cached = await self._get_cached(cache_key)
        if cached is not None:
            return cached

        price = quantize_price(await self.provider.get_price(normalized_symbol))
        await self._set_cached(cache_key, price)
        return price

    async def _get_cached(self, key: str) -> Decimal | None:
        try:
            value = await self.cache.get(key)
            if value is None:
                return None
            if isinstance(value, bytes):
                value = value.decode("utf-8")
            price = quantize_price(Decimal(value))
            return price if price > 0 else None
        except (RedisError, ConnectionError, OSError, ValueError, InvalidOperation):
            return None

    async def _set_cached(self, key: str, price: Decimal) -> None:
        try:
            await self.cache.set(key, str(price), ex=self.ttl_seconds)
        except (RedisError, ConnectionError, OSError):
            pass
