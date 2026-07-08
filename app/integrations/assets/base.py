"""Asset lookup integration contracts."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from app.domain.enums import AssetType


@dataclass(frozen=True)
class AssetLookupResult:
    """Normalized asset metadata returned by an external provider."""

    symbol: str
    name: str
    asset_type: AssetType
    currency: str
    exchange: str | None = None
    isin: str | None = None


class AssetLookupProvider(Protocol):
    """Provider capable of resolving a market symbol into asset metadata."""

    async def lookup(self, symbol: str) -> AssetLookupResult:
        """Return metadata for a tradable symbol."""
