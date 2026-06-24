"""Transaction repository."""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.enums import TransactionType
from app.models.transaction import Transaction


class TransactionRepository:
    """Persistence operations for immutable transaction entries."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_for_portfolio(self, portfolio_id: uuid.UUID) -> Sequence[Transaction]:
        result = await self.session.execute(
            select(Transaction)
            .where(Transaction.portfolio_id == portfolio_id)
            .order_by(Transaction.trade_date, Transaction.created_at, Transaction.id)
        )
        return result.scalars().all()

    async def get_by_idempotency_key(
        self,
        *,
        portfolio_id: uuid.UUID,
        idempotency_key: str,
    ) -> Transaction | None:
        result = await self.session.execute(
            select(Transaction).where(
                Transaction.portfolio_id == portfolio_id,
                Transaction.idempotency_key == idempotency_key,
            )
        )
        return result.scalar_one_or_none()

    async def get_latest_for_asset(
        self,
        *,
        portfolio_id: uuid.UUID,
        asset_id: uuid.UUID,
    ) -> Transaction | None:
        result = await self.session.execute(
            select(Transaction)
            .where(
                Transaction.portfolio_id == portfolio_id,
                Transaction.asset_id == asset_id,
            )
            .order_by(Transaction.trade_date.desc(), Transaction.created_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    def add(
        self,
        *,
        portfolio_id: uuid.UUID,
        asset_id: uuid.UUID,
        transaction_type: TransactionType,
        quantity: Decimal,
        unit_price: Decimal,
        fees: Decimal,
        taxes: Decimal,
        realized_pnl: Decimal,
        currency: str,
        trade_date: datetime,
        settlement_date: date | None,
        notes: str | None,
        idempotency_key: str,
    ) -> Transaction:
        transaction = Transaction(
            portfolio_id=portfolio_id,
            asset_id=asset_id,
            transaction_type=transaction_type,
            quantity=quantity,
            unit_price=unit_price,
            fees=fees,
            taxes=taxes,
            realized_pnl=realized_pnl,
            currency=currency,
            trade_date=trade_date,
            settlement_date=settlement_date,
            notes=notes,
            idempotency_key=idempotency_key,
        )
        self.session.add(transaction)
        return transaction
