"""Alpha Vantage asset metadata lookup provider."""

from __future__ import annotations

from typing import Any

import httpx

from app.core.exceptions import AssetLookupNotFoundError, AssetLookupUnavailableError
from app.domain.enums import AssetType
from app.integrations.assets.base import AssetLookupResult


class AlphaVantageAssetLookupProvider:
    """Fetch asset metadata from Alpha Vantage's SYMBOL_SEARCH endpoint."""

    def __init__(
        self,
        *,
        api_key: str | None,
        base_url: str,
        timeout_seconds: float,
    ) -> None:
        self.api_key = api_key
        self.base_url = base_url
        self.timeout_seconds = timeout_seconds

    async def lookup(self, symbol: str) -> AssetLookupResult:
        if not self.api_key:
            raise AssetLookupUnavailableError("PRICE_API_KEY is not configured")

        normalized_symbol = symbol.strip().upper()
        try:
            async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                response = await client.get(
                    self.base_url,
                    params={
                        "function": "SYMBOL_SEARCH",
                        "keywords": normalized_symbol,
                        "apikey": self.api_key,
                    },
                )
                response.raise_for_status()
                payload = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise AssetLookupUnavailableError(
                f"Could not fetch asset metadata for {normalized_symbol}"
            ) from exc

        return self._parse_result(symbol=normalized_symbol, payload=payload)

    @classmethod
    def _parse_result(cls, *, symbol: str, payload: Any) -> AssetLookupResult:
        if not isinstance(payload, dict):
            raise AssetLookupUnavailableError(f"Invalid asset lookup response for {symbol}")

        matches = payload.get("bestMatches")
        if not isinstance(matches, list):
            provider_message = payload.get("Note") or payload.get("Information")
            if provider_message:
                raise AssetLookupUnavailableError(str(provider_message))
            raise AssetLookupNotFoundError(f"Asset symbol {symbol} was not found")

        candidates = [match for match in matches if isinstance(match, dict)]
        if not candidates:
            raise AssetLookupNotFoundError(f"Asset symbol {symbol} was not found")

        exact_matches = [
            match for match in candidates if cls._read_string(match, "1. symbol").upper() == symbol
        ]
        selected = max(exact_matches or candidates, key=cls._match_score)

        result_symbol = cls._read_string(selected, "1. symbol").upper()
        name = cls._read_string(selected, "2. name")
        currency = cls._read_string(selected, "8. currency").upper()
        if not result_symbol or not name or not currency:
            raise AssetLookupUnavailableError(f"Incomplete asset lookup response for {symbol}")

        region = cls._read_string(selected, "4. region").upper() or None
        return AssetLookupResult(
            symbol=result_symbol,
            name=name,
            asset_type=cls._map_asset_type(cls._read_string(selected, "3. type")),
            currency=currency,
            exchange=region,
        )

    @staticmethod
    def _read_string(payload: dict[str, Any], key: str) -> str:
        value = payload.get(key)
        return value.strip() if isinstance(value, str) else ""

    @staticmethod
    def _match_score(payload: dict[str, Any]) -> float:
        value = payload.get("9. matchScore")
        if not isinstance(value, str):
            return 0
        try:
            return float(value)
        except ValueError:
            return 0

    @staticmethod
    def _map_asset_type(raw_type: str) -> AssetType:
        normalized = raw_type.strip().lower()
        if "etf" in normalized:
            return AssetType.ETF
        if "reit" in normalized:
            return AssetType.REIT
        if "crypto" in normalized or "digital" in normalized:
            return AssetType.CRYPTO
        if "bond" in normalized or "fixed" in normalized:
            return AssetType.FIXED_INCOME
        return AssetType.STOCK
