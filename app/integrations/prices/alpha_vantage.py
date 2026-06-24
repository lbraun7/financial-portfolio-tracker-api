"""Alpha Vantage market price provider."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any

import httpx

from app.core.exceptions import PriceUnavailableError
from app.domain.money import quantize_price


class AlphaVantagePriceProvider:
    """Fetch latest equity quotes from Alpha Vantage's GLOBAL_QUOTE endpoint."""

    def __init__(
        self,
        *,
        api_key: str | None,
        base_url: str,
        timeout_seconds: float,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self.api_key = api_key
        self.base_url = base_url
        self._client = client or httpx.AsyncClient(timeout=timeout_seconds)
        self._owns_client = client is None

    async def get_price(self, symbol: str) -> Decimal:
        if not self.api_key:
            raise PriceUnavailableError("PRICE_API_KEY is not configured")

        try:
            response = await self._client.get(
                self.base_url,
                params={
                    "function": "GLOBAL_QUOTE",
                    "symbol": symbol,
                    "apikey": self.api_key,
                },
            )
            response.raise_for_status()
            payload = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise PriceUnavailableError(f"Could not fetch price for {symbol}") from exc

        return self._parse_price(symbol=symbol, payload=payload)

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    @staticmethod
    def _parse_price(*, symbol: str, payload: Any) -> Decimal:
        if not isinstance(payload, dict):
            raise PriceUnavailableError(f"Invalid price response for {symbol}")

        quote = payload.get("Global Quote")
        raw_price = quote.get("05. price") if isinstance(quote, dict) else None
        if not isinstance(raw_price, str):
            provider_message = payload.get("Note") or payload.get("Information")
            message = (
                str(provider_message) if provider_message else f"Price is unavailable for {symbol}"
            )
            raise PriceUnavailableError(message)

        try:
            price = quantize_price(Decimal(raw_price))
        except (InvalidOperation, ValueError) as exc:
            raise PriceUnavailableError(f"Invalid price for {symbol}") from exc
        if price <= 0:
            raise PriceUnavailableError(f"Invalid price for {symbol}")
        return price
