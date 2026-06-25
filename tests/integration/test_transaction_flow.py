"""Transaction flow through real PostgreSQL repositories."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal

import pytest
from app.domain.enums import AssetType, TransactionType
from app.models.asset import Asset
from app.models.portfolio import Portfolio
from app.models.user import User
from app.schemas.transaction import TransactionCreate
from app.services.transaction import TransactionService
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

pytestmark = pytest.mark.integration


def transaction_payload(
    *,
    asset_id: uuid.UUID,
    transaction_type: TransactionType,
    quantity: str,
    unit_price: str,
    trade_date: datetime,
    fees: str = "0",
    taxes: str = "0",
) -> TransactionCreate:
    return TransactionCreate(
        asset_id=asset_id,
        transaction_type=transaction_type,
        quantity=Decimal(quantity),
        unit_price=Decimal(unit_price),
        fees=Decimal(fees),
        taxes=Decimal(taxes),
        currency="USD",
        trade_date=trade_date,
    )


async def test_buy_then_sell_persists_fifo_position_and_realized_pnl(
    db_session: AsyncSession,
) -> None:
    user = User(email="integration@example.com", hashed_password="hash", full_name=None)
    asset = Asset(
        symbol="AAPL",
        name="Apple Inc.",
        asset_type=AssetType.STOCK,
        currency="USD",
        exchange="NASDAQ",
        isin=None,
    )
    db_session.add_all([user, asset])
    await db_session.flush()
    portfolio = Portfolio(
        user_id=user.id,
        name="Integration",
        description=None,
        base_currency="USD",
    )
    db_session.add(portfolio)
    await db_session.commit()

    service = TransactionService(db_session)
    buy = await service.record(
        portfolio_id=portfolio.id,
        user_id=user.id,
        payload=transaction_payload(
            asset_id=asset.id,
            transaction_type=TransactionType.BUY,
            quantity="10",
            unit_price="100",
            fees="5",
            taxes="2",
            trade_date=datetime(2026, 1, 10, tzinfo=UTC),
        ),
        idempotency_key="integration-buy",
    )
    sell = await service.record(
        portfolio_id=portfolio.id,
        user_id=user.id,
        payload=transaction_payload(
            asset_id=asset.id,
            transaction_type=TransactionType.SELL,
            quantity="4",
            unit_price="130",
            fees="2",
            taxes="1",
            trade_date=datetime(2026, 2, 10, tzinfo=UTC),
        ),
        idempotency_key="integration-sell",
    )

    positions = await service.list_positions(portfolio_id=portfolio.id, user_id=user.id)
    transactions = await service.list_transactions(portfolio_id=portfolio.id, user_id=user.id)
    position = positions[0]

    result = await db_session.execute(
        select(type(position))
        .options(selectinload(type(position).lots))
        .where(type(position).id == position.id)
    )
    persisted_position = result.scalar_one()

    assert buy.realized_pnl == Decimal("0.0000")
    assert sell.realized_pnl == Decimal("114.2000")
    assert [transaction.id for transaction in transactions] == [buy.id, sell.id]
    assert persisted_position.quantity == Decimal("6.0000000000")
    assert persisted_position.average_cost == Decimal("100.7000000000")
    assert persisted_position.realized_pnl == Decimal("114.2000")
    assert persisted_position.lots[0].quantity_open == Decimal("6.0000000000")
