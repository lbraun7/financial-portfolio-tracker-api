"""Portfolio summary service tests."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal

import pytest
from app.core.exceptions import PortfolioCurrencyMismatchError, PortfolioNotFoundError
from app.domain.enums import AssetType
from app.models.asset import Asset
from app.models.portfolio import Portfolio
from app.models.position import Position
from app.services.summary import PortfolioSummaryService


def make_portfolio(*, base_currency: str = "USD") -> Portfolio:
    now = datetime.now(UTC)
    return Portfolio(
        id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        name="Growth",
        description=None,
        base_currency=base_currency,
        created_at=now,
        updated_at=now,
    )


def make_position(
    portfolio: Portfolio,
    *,
    symbol: str,
    currency: str = "USD",
    quantity: str = "10",
    average_cost: str = "150",
    realized_pnl: str = "0",
) -> Position:
    now = datetime.now(UTC)
    asset = Asset(
        id=uuid.uuid4(),
        symbol=symbol,
        name=symbol,
        asset_type=AssetType.STOCK,
        currency=currency,
        exchange=None,
        isin=None,
        created_at=now,
        updated_at=now,
    )
    return Position(
        id=uuid.uuid4(),
        portfolio_id=portfolio.id,
        asset_id=asset.id,
        quantity=Decimal(quantity),
        average_cost=Decimal(average_cost),
        realized_pnl=Decimal(realized_pnl),
        asset=asset,
        created_at=now,
        updated_at=now,
    )


class StubPrices:
    def __init__(self, prices: dict[str, Decimal]) -> None:
        self.prices = prices

    async def get_price(self, symbol: str) -> Decimal:
        return self.prices[symbol]


class StubPortfolios:
    def __init__(self, portfolio: Portfolio | None) -> None:
        self.portfolio = portfolio

    async def get_for_user(self, **_kwargs: object) -> Portfolio | None:
        return self.portfolio


class StubPositions:
    def __init__(self, positions: list[Position]) -> None:
        self.positions = positions

    async def list_for_portfolio(self, _portfolio_id: uuid.UUID) -> list[Position]:
        return self.positions


def make_service(
    *,
    portfolio: Portfolio | None,
    positions: list[Position],
    prices: dict[str, Decimal],
) -> PortfolioSummaryService:
    service = PortfolioSummaryService(object(), StubPrices(prices))  # type: ignore[arg-type]
    service.portfolios = StubPortfolios(portfolio)  # type: ignore[assignment]
    service.positions = StubPositions(positions)  # type: ignore[assignment]
    return service


async def test_summary_aggregates_current_and_realized_pnl() -> None:
    portfolio = make_portfolio()
    positions = [
        make_position(
            portfolio,
            symbol="AAPL",
            quantity="10",
            average_cost="150",
            realized_pnl="20",
        ),
        make_position(
            portfolio,
            symbol="MSFT",
            quantity="2",
            average_cost="300",
            realized_pnl="-5",
        ),
    ]
    service = make_service(
        portfolio=portfolio,
        positions=positions,
        prices={"AAPL": Decimal("178.5"), "MSFT": Decimal("330")},
    )

    summary = await service.get_summary(
        portfolio_id=portfolio.id,
        user_id=portfolio.user_id,
    )

    assert summary.total_invested == Decimal("2100.0000")
    assert summary.current_value == Decimal("2445.0000")
    assert summary.unrealized_pnl == Decimal("345.0000")
    assert summary.unrealized_pnl_pct == Decimal("16.4286")
    assert summary.realized_pnl == Decimal("15.0000")
    assert summary.positions[0].unrealized_pnl == Decimal("285.0000")
    assert summary.positions[0].unrealized_pnl_pct == Decimal("19.0000")


async def test_summary_keeps_realized_pnl_from_closed_positions() -> None:
    portfolio = make_portfolio()
    closed = make_position(
        portfolio,
        symbol="AAPL",
        quantity="0",
        average_cost="0",
        realized_pnl="125",
    )
    service = make_service(portfolio=portfolio, positions=[closed], prices={})

    summary = await service.get_summary(
        portfolio_id=portfolio.id,
        user_id=portfolio.user_id,
    )

    assert summary.current_value == Decimal("0.0000")
    assert summary.realized_pnl == Decimal("125.0000")
    assert summary.positions == []


async def test_summary_rejects_position_currency_without_fx_conversion() -> None:
    portfolio = make_portfolio(base_currency="USD")
    position = make_position(portfolio, symbol="PETR4.SAO", currency="BRL")
    service = make_service(portfolio=portfolio, positions=[position], prices={})

    with pytest.raises(PortfolioCurrencyMismatchError, match="PETR4.SAO"):
        await service.get_summary(
            portfolio_id=portfolio.id,
            user_id=portfolio.user_id,
        )


async def test_summary_hides_unowned_portfolio() -> None:
    service = make_service(portfolio=None, positions=[], prices={})

    with pytest.raises(PortfolioNotFoundError):
        await service.get_summary(portfolio_id=uuid.uuid4(), user_id=uuid.uuid4())
