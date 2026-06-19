"""Portfolio endpoint tests."""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator, Sequence
from datetime import UTC, datetime

from app.api.v1.portfolios import portfolio_service
from app.core.security import create_access_token, hash_password
from app.db.session import get_async_session
from app.main import create_app
from app.models.portfolio import Portfolio
from app.models.user import User
from app.repositories.users import UserRepository
from app.schemas.portfolio import PortfolioCreate, PortfolioUpdate
from app.services.portfolio import (
    PortfolioNameAlreadyExistsError,
    PortfolioNotFoundError,
    PortfolioService,
)
from fastapi.testclient import TestClient
from pytest import MonkeyPatch


async def fake_session() -> AsyncIterator[object]:
    yield object()


def make_user(*, user_id: uuid.UUID | None = None) -> User:
    """Build a current user for auth dependency tests."""

    return User(
        id=user_id or uuid.uuid4(),
        email="ada@example.com",
        hashed_password=hash_password("correct-password"),
        full_name="Ada Lovelace",
        is_active=True,
        created_at=datetime.now(UTC),
    )


def make_portfolio(
    *,
    portfolio_id: uuid.UUID | None = None,
    user_id: uuid.UUID | None = None,
    name: str = "Long term",
    base_currency: str = "USD",
) -> Portfolio:
    """Build a portfolio response model."""

    now = datetime.now(UTC)
    return Portfolio(
        id=portfolio_id or uuid.uuid4(),
        user_id=user_id or uuid.uuid4(),
        name=name,
        description="Core holdings",
        base_currency=base_currency,
        created_at=now,
        updated_at=now,
    )


def build_client(
    monkeypatch: MonkeyPatch,
    *,
    user: User | None = None,
    service: PortfolioService | None = None,
) -> tuple[TestClient, User]:
    """Return a test client with auth and DB dependencies replaced."""

    current_user = user or make_user()

    async def get_by_id(_self: object, token_user_id: str) -> User | None:
        assert token_user_id == str(current_user.id)
        return current_user

    monkeypatch.setattr(UserRepository, "get_by_id", get_by_id)

    app = create_app()
    app.dependency_overrides[get_async_session] = fake_session
    if service is not None:
        app.dependency_overrides[portfolio_service] = lambda: service

    return TestClient(app), current_user


def auth_headers(user: User) -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token(str(user.id))}"}


def test_list_portfolios_returns_current_users_portfolios(monkeypatch: MonkeyPatch) -> None:
    user = make_user()
    portfolios = [make_portfolio(user_id=user.id), make_portfolio(user_id=user.id, name="BR")]

    class StubService:
        async def list_portfolios(self, user_id: uuid.UUID) -> Sequence[Portfolio]:
            assert user_id == user.id
            return portfolios

    client, current_user = build_client(monkeypatch, user=user, service=StubService())  # type: ignore[arg-type]

    with client:
        response = client.get("/api/v1/portfolios", headers=auth_headers(current_user))

    assert response.status_code == 200
    assert [item["name"] for item in response.json()] == ["Long term", "BR"]


def test_create_portfolio_normalizes_payload(monkeypatch: MonkeyPatch) -> None:
    user = make_user()
    captured: dict[str, object] = {}

    class StubService:
        async def create_portfolio(
            self,
            *,
            payload: PortfolioCreate,
            user_id: uuid.UUID,
        ) -> Portfolio:
            captured["payload"] = payload
            captured["user_id"] = user_id
            return make_portfolio(
                user_id=user_id,
                name=payload.name,
                base_currency=payload.base_currency,
            )

    client, current_user = build_client(monkeypatch, user=user, service=StubService())  # type: ignore[arg-type]

    with client:
        response = client.post(
            "/api/v1/portfolios",
            headers=auth_headers(current_user),
            json={
                "name": " Growth ",
                "description": "  ",
                "base_currency": "brl",
            },
        )

    payload = captured["payload"]
    assert response.status_code == 201
    assert response.json()["name"] == "Growth"
    assert isinstance(payload, PortfolioCreate)
    assert payload.description is None
    assert payload.base_currency == "BRL"
    assert captured["user_id"] == user.id


def test_create_portfolio_rejects_duplicate_name(monkeypatch: MonkeyPatch) -> None:
    class StubService:
        async def create_portfolio(
            self,
            *,
            payload: PortfolioCreate,
            user_id: uuid.UUID,
        ) -> Portfolio:
            raise PortfolioNameAlreadyExistsError

    client, current_user = build_client(monkeypatch, service=StubService())  # type: ignore[arg-type]

    with client:
        response = client.post(
            "/api/v1/portfolios",
            headers=auth_headers(current_user),
            json={"name": "Long term"},
        )

    assert response.status_code == 409


def test_get_portfolio_returns_404_when_not_owned(monkeypatch: MonkeyPatch) -> None:
    class StubService:
        async def get_portfolio(self, *, portfolio_id: uuid.UUID, user_id: uuid.UUID) -> Portfolio:
            raise PortfolioNotFoundError

    client, current_user = build_client(monkeypatch, service=StubService())  # type: ignore[arg-type]

    with client:
        response = client.get(
            f"/api/v1/portfolios/{uuid.uuid4()}",
            headers=auth_headers(current_user),
        )

    assert response.status_code == 404


def test_update_portfolio_patches_owned_portfolio(monkeypatch: MonkeyPatch) -> None:
    user = make_user()
    portfolio_id = uuid.uuid4()
    captured: dict[str, object] = {}

    class StubService:
        async def update_portfolio(
            self,
            *,
            portfolio_id: uuid.UUID,
            payload: PortfolioUpdate,
            user_id: uuid.UUID,
        ) -> Portfolio:
            captured["portfolio_id"] = portfolio_id
            captured["payload"] = payload
            captured["user_id"] = user_id
            return make_portfolio(
                portfolio_id=portfolio_id,
                user_id=user_id,
                name=payload.name or "Long term",
                base_currency=payload.base_currency or "USD",
            )

    client, current_user = build_client(monkeypatch, user=user, service=StubService())  # type: ignore[arg-type]

    with client:
        response = client.patch(
            f"/api/v1/portfolios/{portfolio_id}",
            headers=auth_headers(current_user),
            json={"name": " Retirement ", "base_currency": "eur"},
        )

    payload = captured["payload"]
    assert response.status_code == 200
    assert response.json()["name"] == "Retirement"
    assert isinstance(payload, PortfolioUpdate)
    assert payload.base_currency == "EUR"
    assert captured["portfolio_id"] == portfolio_id
    assert captured["user_id"] == user.id


def test_delete_portfolio_returns_no_content(monkeypatch: MonkeyPatch) -> None:
    user = make_user()
    portfolio_id = uuid.uuid4()
    captured: dict[str, uuid.UUID] = {}

    class StubService:
        async def delete_portfolio(self, *, portfolio_id: uuid.UUID, user_id: uuid.UUID) -> None:
            captured["portfolio_id"] = portfolio_id
            captured["user_id"] = user_id

    client, current_user = build_client(monkeypatch, user=user, service=StubService())  # type: ignore[arg-type]

    with client:
        response = client.delete(
            f"/api/v1/portfolios/{portfolio_id}",
            headers=auth_headers(current_user),
        )

    assert response.status_code == 204
    assert captured == {"portfolio_id": portfolio_id, "user_id": user.id}


def test_portfolio_endpoints_require_authentication(monkeypatch: MonkeyPatch) -> None:
    client, _current_user = build_client(monkeypatch)

    with client:
        response = client.get("/api/v1/portfolios")

    assert response.status_code == 401
