"""Portfolio valuation and P&L summary service."""

from __future__ import annotations

import asyncio
import uuid
from collections.abc import Sequence
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import PortfolioCurrencyMismatchError, PortfolioNotFoundError
from app.domain.money import ZERO_DECIMAL, quantize_money
from app.domain.pnl import calculate_unrealized_pnl
from app.models.position import Position
from app.repositories.portfolios import PortfolioRepository
from app.repositories.positions import PositionRepository
from app.schemas.summary import PortfolioSummary, PositionSummary
from app.services.price import PriceService


class PortfolioSummaryService:
    """Build an on-demand portfolio valuation from positions and market prices."""

    def __init__(self, session: AsyncSession, price_service: PriceService) -> None:
        self.portfolios = PortfolioRepository(session)
        self.positions = PositionRepository(session)
        self.price_service = price_service

    async def get_summary(
        self,
        *,
        portfolio_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> PortfolioSummary:
        portfolio = await self.portfolios.get_for_user(
            portfolio_id=portfolio_id,
            user_id=user_id,
        )
        if portfolio is None:
            raise PortfolioNotFoundError

        positions = await self.positions.list_for_portfolio(portfolio_id)
        open_positions = [position for position in positions if position.quantity > ZERO_DECIMAL]
        mismatched = [
            position.asset.symbol
            for position in open_positions
            if position.asset.currency != portfolio.base_currency
        ]
        if mismatched:
            symbols = ", ".join(mismatched)
            raise PortfolioCurrencyMismatchError(
                f"Positions are not denominated in {portfolio.base_currency}: {symbols}"
            )

        prices = await asyncio.gather(
            *(self.price_service.get_price(position.asset.symbol) for position in open_positions)
        )
        position_summaries = self._summarize_positions(open_positions, prices)

        total_invested = quantize_money(
            sum((item.invested for item in position_summaries), start=ZERO_DECIMAL)
        )
        current_value = quantize_money(
            sum((item.current_value for item in position_summaries), start=ZERO_DECIMAL)
        )
        unrealized_pnl = quantize_money(current_value - total_invested)
        unrealized_pnl_pct = (
            ZERO_DECIMAL
            if total_invested == ZERO_DECIMAL
            else quantize_money((unrealized_pnl / total_invested) * Decimal("100"))
        )
        realized_pnl = quantize_money(
            sum((position.realized_pnl for position in positions), start=ZERO_DECIMAL)
        )

        return PortfolioSummary(
            portfolio_id=portfolio.id,
            base_currency=portfolio.base_currency,
            total_invested=total_invested,
            current_value=current_value,
            unrealized_pnl=unrealized_pnl,
            unrealized_pnl_pct=unrealized_pnl_pct,
            realized_pnl=realized_pnl,
            positions=position_summaries,
        )

    @staticmethod
    def _summarize_positions(
        positions: Sequence[Position],
        prices: Sequence[Decimal],
    ) -> list[PositionSummary]:
        summaries: list[PositionSummary] = []
        for position, current_price in zip(positions, prices, strict=True):
            valuation = calculate_unrealized_pnl(
                quantity=position.quantity,
                average_cost=position.average_cost,
                current_price=current_price,
            )
            summaries.append(
                PositionSummary(
                    asset_id=position.asset_id,
                    ticker=position.asset.symbol,
                    currency=position.asset.currency,
                    quantity=position.quantity,
                    avg_cost=position.average_cost,
                    current_price=current_price,
                    invested=valuation.cost_basis,
                    current_value=valuation.current_value,
                    unrealized_pnl=valuation.amount,
                    unrealized_pnl_pct=valuation.percentage,
                    realized_pnl=position.realized_pnl,
                )
            )
        return summaries
