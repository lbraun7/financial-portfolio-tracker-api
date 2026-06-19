"""Portfolio use cases."""

from __future__ import annotations

import uuid
from collections.abc import Sequence

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.portfolio import Portfolio
from app.repositories.portfolios import PortfolioRepository
from app.schemas.portfolio import PortfolioCreate, PortfolioUpdate


class PortfolioNotFoundError(Exception):
    """Raised when a portfolio is absent or not owned by the user."""


class PortfolioNameAlreadyExistsError(Exception):
    """Raised when a user already has a portfolio with the requested name."""


class PortfolioService:
    """Portfolio use cases with ownership checks."""

    def __init__(self, session: AsyncSession) -> None:
        self.repository = PortfolioRepository(session)

    async def list_portfolios(self, user_id: uuid.UUID) -> Sequence[Portfolio]:
        """List portfolios owned by a user."""

        return await self.repository.list_for_user(user_id)

    async def get_portfolio(self, *, portfolio_id: uuid.UUID, user_id: uuid.UUID) -> Portfolio:
        """Return one portfolio after verifying ownership."""

        portfolio = await self.repository.get_for_user(portfolio_id=portfolio_id, user_id=user_id)
        if portfolio is None:
            raise PortfolioNotFoundError
        return portfolio

    async def create_portfolio(self, *, payload: PortfolioCreate, user_id: uuid.UUID) -> Portfolio:
        """Create a portfolio for a user."""

        existing = await self.repository.get_by_name_for_user(name=payload.name, user_id=user_id)
        if existing is not None:
            raise PortfolioNameAlreadyExistsError

        return await self.repository.create(
            user_id=user_id,
            name=payload.name,
            description=payload.description,
            base_currency=payload.base_currency,
        )

    async def update_portfolio(
        self,
        *,
        portfolio_id: uuid.UUID,
        payload: PortfolioUpdate,
        user_id: uuid.UUID,
    ) -> Portfolio:
        """Update a user's portfolio."""

        portfolio = await self.get_portfolio(portfolio_id=portfolio_id, user_id=user_id)
        update_data = payload.model_dump(exclude_unset=True)

        requested_name = update_data.get("name")
        if isinstance(requested_name, str) and requested_name != portfolio.name:
            existing = await self.repository.get_by_name_for_user(
                name=requested_name,
                user_id=user_id,
            )
            if existing is not None and existing.id != portfolio.id:
                raise PortfolioNameAlreadyExistsError

        return await self.repository.update(
            portfolio,
            name=update_data.get("name"),
            description=update_data.get("description", portfolio.description),
            base_currency=update_data.get("base_currency"),
        )

    async def delete_portfolio(self, *, portfolio_id: uuid.UUID, user_id: uuid.UUID) -> None:
        """Delete a user's portfolio."""

        deleted = await self.repository.delete_for_user(portfolio_id=portfolio_id, user_id=user_id)
        if not deleted:
            raise PortfolioNotFoundError
