"""Transaction endpoint tests."""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from decimal import Decimal

from app.api.v1.transactions import transaction_service
from app.core.exceptions import IdempotencyConflictError
from app.core.security import create_access_token, hash_password
from app.db.session import get_async_session
from app.domain.enums import TransactionType
from app.main import create_app
from app.models.transaction import Transaction
from app.models.user import User
from app.repositories.users import UserRepository
from app.schemas.transaction import TransactionCreate
from app.services.transaction import TransactionService
from fastapi.testclient import TestClient
from pytest import MonkeyPatch


async def fake_session() -> AsyncIterator[object]:
    yield object()


def make_user() -> User:
    return User(
        id=uuid.uuid4(),
        email="ada@example.com",
        hashed_password=hash_password("correct-password"),
        full_name="Ada Lovelace",
        is_active=True,
        created_at=datetime.now(UTC),
    )


def make_transaction(
    *,
    portfolio_id: uuid.UUID,
    asset_id: uuid.UUID,
    idempotency_key: str,
) -> Transaction:
    now = datetime.now(UTC)
    return Transaction(
        id=uuid.uuid4(),
        portfolio_id=portfolio_id,
        asset_id=asset_id,
        transaction_type=TransactionType.BUY,
        quantity=Decimal("10"),
        unit_price=Decimal("100"),
        fees=Decimal("5"),
        taxes=Decimal("2"),
        realized_pnl=Decimal("0"),
        currency="USD",
        trade_date=now,
        settlement_date=None,
        notes=None,
        idempotency_key=idempotency_key,
        created_at=now,
        updated_at=now,
    )


def build_client(
    monkeypatch: MonkeyPatch,
    *,
    service: TransactionService,
) -> tuple[TestClient, User]:
    user = make_user()

    async def get_by_id(_self: object, _user_id: str) -> User:
        return user

    monkeypatch.setattr(UserRepository, "get_by_id", get_by_id)
    app = create_app()
    app.dependency_overrides[get_async_session] = fake_session
    app.dependency_overrides[transaction_service] = lambda: service
    return TestClient(app), user


def auth_headers(user: User, *, idempotency_key: str | None = None) -> dict[str, str]:
    headers = {"Authorization": f"Bearer {create_access_token(str(user.id))}"}
    if idempotency_key is not None:
        headers["Idempotency-Key"] = idempotency_key
    return headers


def transaction_payload(asset_id: uuid.UUID) -> dict[str, str]:
    return {
        "asset_id": str(asset_id),
        "transaction_type": "buy",
        "quantity": "10",
        "unit_price": "100",
        "fees": "5",
        "taxes": "2",
        "currency": "usd",
        "trade_date": "2026-06-23T12:00:00-03:00",
    }


def test_record_transaction_requires_idempotency_key(monkeypatch: MonkeyPatch) -> None:
    class StubService:
        pass

    client, user = build_client(monkeypatch, service=StubService())  # type: ignore[arg-type]

    with client:
        response = client.post(
            f"/api/v1/portfolios/{uuid.uuid4()}/transactions",
            headers=auth_headers(user),
            json=transaction_payload(uuid.uuid4()),
        )

    assert response.status_code == 422


def test_record_transaction_normalizes_and_forwards_payload(monkeypatch: MonkeyPatch) -> None:
    portfolio_id = uuid.uuid4()
    asset_id = uuid.uuid4()
    captured: dict[str, object] = {}

    class StubService:
        async def record(
            self,
            *,
            portfolio_id: uuid.UUID,
            user_id: uuid.UUID,
            payload: TransactionCreate,
            idempotency_key: str,
        ) -> Transaction:
            captured.update(
                portfolio_id=portfolio_id,
                user_id=user_id,
                payload=payload,
                idempotency_key=idempotency_key,
            )
            return make_transaction(
                portfolio_id=portfolio_id,
                asset_id=payload.asset_id,
                idempotency_key=idempotency_key,
            )

    client, user = build_client(monkeypatch, service=StubService())  # type: ignore[arg-type]

    with client:
        response = client.post(
            f"/api/v1/portfolios/{portfolio_id}/transactions",
            headers=auth_headers(user, idempotency_key=" buy-001 "),
            json=transaction_payload(asset_id),
        )

    assert response.status_code == 201
    assert response.json()["idempotency_key"] == "buy-001"
    assert captured["portfolio_id"] == portfolio_id
    assert captured["user_id"] == user.id
    assert captured["idempotency_key"] == "buy-001"
    request_payload = captured["payload"]
    assert isinstance(request_payload, TransactionCreate)
    assert request_payload.currency == "USD"
    assert request_payload.trade_date == datetime(2026, 6, 23, 15, tzinfo=UTC)


def test_record_transaction_maps_idempotency_conflict(monkeypatch: MonkeyPatch) -> None:
    class StubService:
        async def record(self, **_kwargs: object) -> Transaction:
            raise IdempotencyConflictError

    client, user = build_client(monkeypatch, service=StubService())  # type: ignore[arg-type]

    with client:
        response = client.post(
            f"/api/v1/portfolios/{uuid.uuid4()}/transactions",
            headers=auth_headers(user, idempotency_key="same-key"),
            json=transaction_payload(uuid.uuid4()),
        )

    assert response.status_code == 409
    assert "different payload" in response.json()["detail"]
