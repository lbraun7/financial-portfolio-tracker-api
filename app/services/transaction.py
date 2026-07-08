"""Transaction engine and position update service."""

from __future__ import annotations

import uuid
from collections.abc import Sequence

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import (
    AssetCurrencyMismatchError,
    AssetNotFoundError,
    IdempotencyConflictError,
    InsufficientPositionError,
    OutOfOrderTransactionError,
    PortfolioNotFoundError,
)
from app.domain.enums import TransactionType
from app.domain.money import ZERO_DECIMAL, quantize_money, quantize_quantity
from app.domain.pnl import (
    FifoLot,
    calculate_average_cost,
    calculate_buy_unit_cost,
    calculate_realized_pnl,
    consume_fifo,
)
from app.models.position import Position
from app.models.transaction import Transaction
from app.repositories.assets import AssetRepository
from app.repositories.portfolios import PortfolioRepository
from app.repositories.positions import PositionRepository
from app.repositories.transactions import TransactionRepository
from app.schemas.transaction import TransactionCreate


class TransactionService:
    """Record immutable transactions and update positions atomically."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.assets = AssetRepository(session)
        self.portfolios = PortfolioRepository(session)
        self.positions = PositionRepository(session)
        self.transactions = TransactionRepository(session)

    async def list_transactions(
        self,
        *,
        portfolio_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> Sequence[Transaction]:
        portfolio = await self.portfolios.get_for_user(
            portfolio_id=portfolio_id,
            user_id=user_id,
        )
        if portfolio is None:
            raise PortfolioNotFoundError
        return await self.transactions.list_for_portfolio(portfolio_id)

    async def list_positions(
        self,
        *,
        portfolio_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> Sequence[Position]:
        portfolio = await self.portfolios.get_for_user(
            portfolio_id=portfolio_id,
            user_id=user_id,
        )
        if portfolio is None:
            raise PortfolioNotFoundError
        return await self.positions.list_for_portfolio(portfolio_id)

    async def record(
        self,
        *,
        portfolio_id: uuid.UUID,
        user_id: uuid.UUID,
        payload: TransactionCreate,
        idempotency_key: str,
    ) -> Transaction:
        """Apply one BUY or SELL as a single database transaction."""

        try:
            portfolio = await self.portfolios.get_for_user_for_update(
                portfolio_id=portfolio_id,
                user_id=user_id,
            )
            if portfolio is None:
                raise PortfolioNotFoundError

            existing = await self.transactions.get_by_idempotency_key(
                portfolio_id=portfolio_id,
                idempotency_key=idempotency_key,
            )
            if existing is not None:
                if not self._matches_payload(existing, payload):
                    raise IdempotencyConflictError
                await self.session.commit()
                return existing

            asset_id = payload.asset_id
            if asset_id is None:
                raise AssetNotFoundError

            asset = await self.assets.get_by_id(asset_id)
            if asset is None:
                raise AssetNotFoundError
            if asset.currency != payload.currency:
                raise AssetCurrencyMismatchError

            latest = await self.transactions.get_latest_for_asset(
                portfolio_id=portfolio_id,
                asset_id=asset_id,
            )
            if latest is not None and payload.trade_date < latest.trade_date:
                raise OutOfOrderTransactionError

            position = await self.positions.get_for_update(
                portfolio_id=portfolio_id,
                asset_id=asset_id,
            )
            if position is None:
                position = self.positions.add_position(
                    portfolio_id=portfolio_id,
                    asset_id=asset_id,
                )
                await self.session.flush()

            if payload.transaction_type == TransactionType.BUY:
                transaction = await self._record_buy(
                    portfolio_id=portfolio_id,
                    position=position,
                    payload=payload,
                    idempotency_key=idempotency_key,
                )
            else:
                transaction = await self._record_sell(
                    portfolio_id=portfolio_id,
                    position=position,
                    payload=payload,
                    idempotency_key=idempotency_key,
                )

            await self.session.commit()
            await self.session.refresh(transaction)
            return transaction
        except Exception:
            await self.session.rollback()
            raise

    async def _record_buy(
        self,
        *,
        portfolio_id: uuid.UUID,
        position: Position,
        payload: TransactionCreate,
        idempotency_key: str,
    ) -> Transaction:
        unit_cost = calculate_buy_unit_cost(
            quantity=payload.quantity,
            unit_price=payload.unit_price,
            fees=payload.fees,
            taxes=payload.taxes,
        )
        existing_lots = await self.positions.list_open_lots_for_update(position.id)
        asset_id = payload.asset_id
        if asset_id is None:
            raise AssetNotFoundError

        transaction = self.transactions.add(
            portfolio_id=portfolio_id,
            asset_id=asset_id,
            transaction_type=payload.transaction_type,
            quantity=payload.quantity,
            unit_price=payload.unit_price,
            fees=payload.fees,
            taxes=payload.taxes,
            realized_pnl=ZERO_DECIMAL,
            currency=payload.currency,
            trade_date=payload.trade_date,
            settlement_date=payload.settlement_date,
            notes=payload.notes,
            idempotency_key=idempotency_key,
        )
        await self.session.flush()
        self.positions.add_lot(
            position_id=position.id,
            source_transaction_id=transaction.id,
            quantity=payload.quantity,
            unit_cost=unit_cost,
            acquired_at=payload.trade_date,
        )

        position.quantity = quantize_quantity(position.quantity + payload.quantity)
        position.average_cost = calculate_average_cost(
            lots=[
                *[
                    FifoLot(quantity=lot.quantity_open, unit_cost=lot.unit_cost)
                    for lot in existing_lots
                ],
                FifoLot(quantity=payload.quantity, unit_cost=unit_cost),
            ]
        )
        return transaction

    async def _record_sell(
        self,
        *,
        portfolio_id: uuid.UUID,
        position: Position,
        payload: TransactionCreate,
        idempotency_key: str,
    ) -> Transaction:
        if position.quantity < payload.quantity:
            raise InsufficientPositionError

        open_lots = list(await self.positions.list_open_lots_for_update(position.id))
        consumption = consume_fifo(
            lots=[
                FifoLot(quantity=lot.quantity_open, unit_cost=lot.unit_cost) for lot in open_lots
            ],
            quantity=payload.quantity,
        )
        for lot, consumed_quantity in zip(
            open_lots,
            consumption.consumed_quantities,
            strict=False,
        ):
            lot.quantity_open = quantize_quantity(lot.quantity_open - consumed_quantity)

        realized_pnl = calculate_realized_pnl(
            quantity=payload.quantity,
            unit_price=payload.unit_price,
            fees=payload.fees,
            taxes=payload.taxes,
            cost_basis=consumption.cost_basis,
        )
        position.quantity = quantize_quantity(position.quantity - payload.quantity)
        position.realized_pnl = quantize_money(position.realized_pnl + realized_pnl)
        position.average_cost = calculate_average_cost(
            lots=[
                FifoLot(quantity=lot.quantity_open, unit_cost=lot.unit_cost)
                for lot in open_lots
                if lot.quantity_open > ZERO_DECIMAL
            ]
        )

        asset_id = payload.asset_id
        if asset_id is None:
            raise AssetNotFoundError

        return self.transactions.add(
            portfolio_id=portfolio_id,
            asset_id=asset_id,
            transaction_type=payload.transaction_type,
            quantity=payload.quantity,
            unit_price=payload.unit_price,
            fees=payload.fees,
            taxes=payload.taxes,
            realized_pnl=realized_pnl,
            currency=payload.currency,
            trade_date=payload.trade_date,
            settlement_date=payload.settlement_date,
            notes=payload.notes,
            idempotency_key=idempotency_key,
        )

    @staticmethod
    def _matches_payload(transaction: Transaction, payload: TransactionCreate) -> bool:
        return (
            transaction.asset_id == payload.asset_id
            and transaction.transaction_type == payload.transaction_type
            and transaction.quantity == payload.quantity
            and transaction.unit_price == payload.unit_price
            and transaction.fees == payload.fees
            and transaction.taxes == payload.taxes
            and transaction.currency == payload.currency
            and transaction.trade_date == payload.trade_date
            and transaction.settlement_date == payload.settlement_date
            and transaction.notes == payload.notes
        )
