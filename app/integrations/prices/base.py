"""Price provider contracts."""

from __future__ import annotations

from decimal import Decimal
from typing import Protocol


class PriceProvider(Protocol):
    """External source capable of returning one current market price."""

    async def get_price(self, symbol: str) -> Decimal:
        """Return the latest available price for a provider symbol."""
