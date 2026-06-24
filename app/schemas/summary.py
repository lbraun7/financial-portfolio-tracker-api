"""Portfolio valuation schemas."""

from __future__ import annotations

import uuid
from decimal import Decimal

from pydantic import BaseModel


class PositionSummary(BaseModel):
    """Current valuation of one open portfolio position."""

    asset_id: uuid.UUID
    ticker: str
    currency: str
    quantity: Decimal
    avg_cost: Decimal
    current_price: Decimal
    invested: Decimal
    current_value: Decimal
    unrealized_pnl: Decimal
    unrealized_pnl_pct: Decimal
    realized_pnl: Decimal


class PortfolioSummary(BaseModel):
    """Aggregated current portfolio valuation."""

    portfolio_id: uuid.UUID
    base_currency: str
    total_invested: Decimal
    current_value: Decimal
    unrealized_pnl: Decimal
    unrealized_pnl_pct: Decimal
    realized_pnl: Decimal
    positions: list[PositionSummary]
