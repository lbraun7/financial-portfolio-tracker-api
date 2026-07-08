"""Alpha Vantage asset lookup provider tests."""

from __future__ import annotations

import pytest
from app.core.exceptions import AssetLookupNotFoundError, AssetLookupUnavailableError
from app.domain.enums import AssetType
from app.integrations.assets.alpha_vantage import AlphaVantageAssetLookupProvider


def test_parse_result_prefers_exact_symbol_match() -> None:
    payload = {
        "bestMatches": [
            {
                "1. symbol": "AAPL34.SAO",
                "2. name": "Apple Inc. BDR",
                "3. type": "Equity",
                "4. region": "Brazil/Sao Paolo",
                "8. currency": "BRL",
                "9. matchScore": "0.9000",
            },
            {
                "1. symbol": "AAPL",
                "2. name": "Apple Inc.",
                "3. type": "Equity",
                "4. region": "United States",
                "8. currency": "USD",
                "9. matchScore": "0.8000",
            },
        ]
    }

    result = AlphaVantageAssetLookupProvider._parse_result(symbol="AAPL", payload=payload)

    assert result.symbol == "AAPL"
    assert result.name == "Apple Inc."
    assert result.asset_type == AssetType.STOCK
    assert result.currency == "USD"
    assert result.exchange == "UNITED STATES"


def test_parse_result_maps_etf_type() -> None:
    payload = {
        "bestMatches": [
            {
                "1. symbol": "SPY",
                "2. name": "SPDR S&P 500 ETF Trust",
                "3. type": "ETF",
                "4. region": "United States",
                "8. currency": "USD",
                "9. matchScore": "1.0000",
            }
        ]
    }

    result = AlphaVantageAssetLookupProvider._parse_result(symbol="SPY", payload=payload)

    assert result.asset_type == AssetType.ETF


def test_parse_result_raises_when_no_matches() -> None:
    with pytest.raises(AssetLookupNotFoundError):
        AlphaVantageAssetLookupProvider._parse_result(symbol="NOPE", payload={"bestMatches": []})


def test_parse_result_maps_provider_message_to_unavailable() -> None:
    with pytest.raises(AssetLookupUnavailableError):
        AlphaVantageAssetLookupProvider._parse_result(
            symbol="AAPL",
            payload={"Information": "rate limit"},
        )
