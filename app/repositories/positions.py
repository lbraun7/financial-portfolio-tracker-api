"""Position repository."""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from datetime import datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.domain.money import ZERO_DECIMAL
from app.models.position import Position
from app.models.position_lot import PositionLot


class PositionRepository:
    """Persistence operations for materialized positions and FIFO lots."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_for_portfolio(self, portfolio_id: uuid.UUID) -> Sequence[Position]:
        result = await self.session.execute(
            select(Position)
            .options(selectinload(Position.asset))
            .where(Position.portfolio_id == portfolio_id)
            .order_by(Position.created_at, Position.id)
        )
        return result.scalars().all()

    async def get_for_update(
        self,
        *,
        portfolio_id: uuid.UUID,
        asset_id: uuid.UUID,
    ) -> Position | None:
        result = await self.session.execute(
            select(Position)
            .where(
                Position.portfolio_id == portfolio_id,
                Position.asset_id == asset_id,
            )
            .with_for_update()
        )
        return result.scalar_one_or_none()

    def add_position(self, *, portfolio_id: uuid.UUID, asset_id: uuid.UUID) -> Position:
        position = Position(
            portfolio_id=portfolio_id,
            asset_id=asset_id,
            quantity=ZERO_DECIMAL,
            average_cost=ZERO_DECIMAL,
            realized_pnl=ZERO_DECIMAL,
        )
        self.session.add(position)
        return position

    async def list_open_lots_for_update(self, position_id: uuid.UUID) -> Sequence[PositionLot]:
        result = await self.session.execute(
            select(PositionLot)
            .where(
                PositionLot.position_id == position_id,
                PositionLot.quantity_open > ZERO_DECIMAL,
            )
            .order_by(
                PositionLot.acquired_at,
                PositionLot.created_at,
                PositionLot.id,
            )
            .with_for_update()
        )
        return result.scalars().all()

    def add_lot(
        self,
        *,
        position_id: uuid.UUID,
        source_transaction_id: uuid.UUID,
        quantity: Decimal,
        unit_cost: Decimal,
        acquired_at: datetime,
    ) -> PositionLot:
        lot = PositionLot(
            position_id=position_id,
            source_transaction_id=source_transaction_id,
            quantity_initial=quantity,
            quantity_open=quantity,
            unit_cost=unit_cost,
            acquired_at=acquired_at,
        )
        self.session.add(lot)
        return lot
