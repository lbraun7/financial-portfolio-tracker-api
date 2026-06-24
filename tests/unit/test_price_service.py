"""Market price provider and cache tests."""

from __future__ import annotations

from decimal import Decimal

import httpx
import pytest
from app.core.exceptions import PriceUnavailableError
from app.integrations.prices.alpha_vantage import AlphaVantagePriceProvider
from app.services.price import PriceService


class MemoryCache:
    def __init__(self) -> None:
        self.values: dict[str, str] = {}
        self.set_calls: list[tuple[str, str, int]] = []

    async def get(self, key: str) -> str | None:
        return self.values.get(key)

    async def set(self, key: str, value: str, *, ex: int) -> None:
        self.values[key] = value
        self.set_calls.append((key, value, ex))


class StubProvider:
    def __init__(self, price: Decimal) -> None:
        self.price = price
        self.symbols: list[str] = []

    async def get_price(self, symbol: str) -> Decimal:
        self.symbols.append(symbol)
        return self.price


async def test_price_service_caches_normalized_provider_price() -> None:
    cache = MemoryCache()
    provider = StubProvider(Decimal("178.5"))
    service = PriceService(provider=provider, cache=cache, ttl_seconds=300)

    first = await service.get_price(" aapl ")
    second = await service.get_price("AAPL")

    assert first == Decimal("178.5000000000")
    assert second == first
    assert provider.symbols == ["AAPL"]
    assert cache.set_calls == [
        ("market-price:AAPL", "178.5000000000", 300),
    ]


async def test_price_service_falls_back_when_cache_is_unavailable() -> None:
    class BrokenCache:
        async def get(self, _key: str) -> str | None:
            raise ConnectionError

        async def set(self, _key: str, _value: str, *, ex: int) -> None:
            raise ConnectionError

    provider = StubProvider(Decimal("12.34"))
    service = PriceService(provider=provider, cache=BrokenCache(), ttl_seconds=60)

    assert await service.get_price("PETR4.SAO") == Decimal("12.3400000000")
    assert provider.symbols == ["PETR4.SAO"]


async def test_alpha_vantage_provider_parses_global_quote() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.params["function"] == "GLOBAL_QUOTE"
        assert request.url.params["symbol"] == "AAPL"
        assert request.url.params["apikey"] == "secret"
        return httpx.Response(200, json={"Global Quote": {"05. price": "178.50"}})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        provider = AlphaVantagePriceProvider(
            api_key="secret",
            base_url="https://example.test/query",
            timeout_seconds=1,
            client=client,
        )
        assert await provider.get_price("AAPL") == Decimal("178.5000000000")


async def test_alpha_vantage_provider_maps_rate_limit_response() -> None:
    async def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"Note": "API call frequency exceeded"})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        provider = AlphaVantagePriceProvider(
            api_key="secret",
            base_url="https://example.test/query",
            timeout_seconds=1,
            client=client,
        )
        with pytest.raises(PriceUnavailableError, match="frequency exceeded"):
            await provider.get_price("AAPL")


async def test_alpha_vantage_provider_requires_api_key() -> None:
    provider = AlphaVantagePriceProvider(
        api_key=None,
        base_url="https://example.test/query",
        timeout_seconds=1,
    )
    try:
        with pytest.raises(PriceUnavailableError, match="not configured"):
            await provider.get_price("AAPL")
    finally:
        await provider.aclose()
