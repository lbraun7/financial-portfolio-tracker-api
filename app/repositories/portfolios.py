"""Portfolio repository."""

from __future__ import annotations

import uuid
from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.portfolio import Portfolio


class PortfolioRepository:
    """Persistence operations for portfolios."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_for_user(self, user_id: uuid.UUID) -> Sequence[Portfolio]:
        """Return all portfolios owned by a user."""

        result = await self.session.execute(
            select(Portfolio).where(Portfolio.user_id == user_id).order_by(Portfolio.created_at)
        )
        return result.scalars().all()

    async def get_for_user(
        self,
        *,
        portfolio_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> Portfolio | None:
        """Return a portfolio only when it belongs to the user."""

        result = await self.session.execute(
            select(Portfolio).where(Portfolio.id == portfolio_id, Portfolio.user_id == user_id)
        )
        return result.scalar_one_or_none()

    async def get_by_name_for_user(self, *, name: str, user_id: uuid.UUID) -> Portfolio | None:
        """Return a user's portfolio by exact normalized name."""

        result = await self.session.execute(
            select(Portfolio).where(Portfolio.user_id == user_id, Portfolio.name == name)
        )
        return result.scalar_one_or_none()

    async def create(
        self,
        *,
        user_id: uuid.UUID,
        name: str,
        description: str | None,
        base_currency: str,
    ) -> Portfolio:
        """Create and persist a portfolio."""

        portfolio = Portfolio(
            user_id=user_id,
            name=name,
            description=description,
            base_currency=base_currency,
        )
        self.session.add(portfolio)
        await self.session.commit()
        await self.session.refresh(portfolio)
        return portfolio

    async def update(
        self,
        portfolio: Portfolio,
        *,
        name: str | None = None,
        description: str | None = None,
        base_currency: str | None = None,
    ) -> Portfolio:
        """Persist changed portfolio fields."""

        if name is not None:
            portfolio.name = name
        portfolio.description = description
        if base_currency is not None:
            portfolio.base_currency = base_currency

        await self.session.commit()
        await self.session.refresh(portfolio)
        return portfolio

    async def delete_for_user(self, *, portfolio_id: uuid.UUID, user_id: uuid.UUID) -> bool:
        """Delete a portfolio only when it belongs to the user."""

        portfolio = await self.get_for_user(portfolio_id=portfolio_id, user_id=user_id)
        if portfolio is None:
            return False

        await self.session.delete(portfolio)
        await self.session.commit()
        return True
