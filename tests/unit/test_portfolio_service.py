"""Portfolio service tests."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest
from app.core.exceptions import PortfolioNameAlreadyExistsError, PortfolioNotFoundError
from app.models.portfolio import Portfolio
from app.schemas.portfolio import PortfolioCreate, PortfolioUpdate
from app.services.portfolio import PortfolioService


def make_portfolio(
    *,
    user_id: uuid.UUID,
    portfolio_id: uuid.UUID | None = None,
    name: str = "Growth",
) -> Portfolio:
    now = datetime.now(UTC)
    return Portfolio(
        id=portfolio_id or uuid.uuid4(),
        user_id=user_id,
        name=name,
        description="Core holdings",
        base_currency="USD",
        created_at=now,
        updated_at=now,
    )


class PortfolioRepositoryStub:
    def __init__(self, portfolios: list[Portfolio] | None = None) -> None:
        self.portfolios = portfolios or []
        self.created: dict[str, object] | None = None
        self.updated: dict[str, object] | None = None
        self.deleted = True

    async def list_for_user(self, user_id: uuid.UUID) -> list[Portfolio]:
        return [portfolio for portfolio in self.portfolios if portfolio.user_id == user_id]

    async def get_for_user(
        self,
        *,
        portfolio_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> Portfolio | None:
        return next(
            (
                portfolio
                for portfolio in self.portfolios
                if portfolio.id == portfolio_id and portfolio.user_id == user_id
            ),
            None,
        )

    async def get_by_name_for_user(
        self,
        *,
        name: str,
        user_id: uuid.UUID,
    ) -> Portfolio | None:
        return next(
            (
                portfolio
                for portfolio in self.portfolios
                if portfolio.name == name and portfolio.user_id == user_id
            ),
            None,
        )

    async def create(self, **kwargs: object) -> Portfolio:
        self.created = kwargs
        portfolio = make_portfolio(
            user_id=kwargs["user_id"],  # type: ignore[arg-type]
            name=kwargs["name"],  # type: ignore[arg-type]
        )
        portfolio.description = kwargs["description"]  # type: ignore[assignment]
        portfolio.base_currency = kwargs["base_currency"]  # type: ignore[assignment]
        return portfolio

    async def update(self, portfolio: Portfolio, **kwargs: object) -> Portfolio:
        self.updated = kwargs
        if kwargs["name"] is not None:
            portfolio.name = kwargs["name"]  # type: ignore[assignment]
        portfolio.description = kwargs["description"]  # type: ignore[assignment]
        if kwargs["base_currency"] is not None:
            portfolio.base_currency = kwargs["base_currency"]  # type: ignore[assignment]
        return portfolio

    async def delete_for_user(self, **_kwargs: object) -> bool:
        return self.deleted


def make_service(repository: PortfolioRepositoryStub) -> PortfolioService:
    service = PortfolioService(object())  # type: ignore[arg-type]
    service.repository = repository  # type: ignore[assignment]
    return service


async def test_list_and_get_portfolios_enforce_ownership() -> None:
    owner_id = uuid.uuid4()
    owned = make_portfolio(user_id=owner_id)
    foreign = make_portfolio(user_id=uuid.uuid4())
    service = make_service(PortfolioRepositoryStub([owned, foreign]))

    assert await service.list_portfolios(owner_id) == [owned]
    assert await service.get_portfolio(portfolio_id=owned.id, user_id=owner_id) is owned

    with pytest.raises(PortfolioNotFoundError):
        await service.get_portfolio(portfolio_id=foreign.id, user_id=owner_id)


async def test_create_portfolio_rejects_duplicate_and_forwards_payload() -> None:
    user_id = uuid.uuid4()
    existing = make_portfolio(user_id=user_id)
    repository = PortfolioRepositoryStub([existing])
    service = make_service(repository)

    with pytest.raises(PortfolioNameAlreadyExistsError):
        await service.create_portfolio(
            payload=PortfolioCreate(name="Growth"),
            user_id=user_id,
        )

    created = await service.create_portfolio(
        payload=PortfolioCreate(name="Retirement", description="Long term", base_currency="BRL"),
        user_id=user_id,
    )

    assert created.name == "Retirement"
    assert repository.created == {
        "user_id": user_id,
        "name": "Retirement",
        "description": "Long term",
        "base_currency": "BRL",
    }


async def test_update_portfolio_checks_name_collision_and_preserves_omitted_fields() -> None:
    user_id = uuid.uuid4()
    portfolio = make_portfolio(user_id=user_id)
    duplicate = make_portfolio(user_id=user_id, name="Retirement")
    repository = PortfolioRepositoryStub([portfolio, duplicate])
    service = make_service(repository)

    with pytest.raises(PortfolioNameAlreadyExistsError):
        await service.update_portfolio(
            portfolio_id=portfolio.id,
            payload=PortfolioUpdate(name="Retirement"),
            user_id=user_id,
        )

    updated = await service.update_portfolio(
        portfolio_id=portfolio.id,
        payload=PortfolioUpdate(description=None, base_currency="EUR"),
        user_id=user_id,
    )

    assert updated.description is None
    assert updated.base_currency == "EUR"
    assert repository.updated == {
        "name": None,
        "description": None,
        "base_currency": "EUR",
    }


async def test_delete_portfolio_maps_missing_row_to_not_found() -> None:
    repository = PortfolioRepositoryStub()
    repository.deleted = False
    service = make_service(repository)

    with pytest.raises(PortfolioNotFoundError):
        await service.delete_portfolio(portfolio_id=uuid.uuid4(), user_id=uuid.uuid4())

    repository.deleted = True
    await service.delete_portfolio(portfolio_id=uuid.uuid4(), user_id=uuid.uuid4())
