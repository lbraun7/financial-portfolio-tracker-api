"""Asset endpoint tests."""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime

from app.api.v1.assets import asset_service
from app.core.exceptions import (
    AssetAlreadyExistsError,
    AssetLookupNotFoundError,
    AssetLookupUnavailableError,
    AssetNotFoundError,
)
from app.core.security import create_access_token, hash_password
from app.db.session import get_async_session
from app.domain.enums import AssetType
from app.main import create_app
from app.models.asset import Asset
from app.models.user import User
from app.repositories.users import UserRepository
from app.schemas.asset import AssetCreate
from app.services.asset import AssetService
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


def make_asset(**overrides: object) -> Asset:
    now = datetime.now(UTC)
    values = {
        "id": uuid.uuid4(),
        "symbol": "AAPL",
        "name": "Apple Inc.",
        "asset_type": AssetType.STOCK,
        "currency": "USD",
        "exchange": "NASDAQ",
        "isin": None,
        "created_at": now,
        "updated_at": now,
    }
    values.update(overrides)
    return Asset(**values)


def build_client(monkeypatch: MonkeyPatch, *, service: AssetService) -> tuple[TestClient, User]:
    user = make_user()

    async def get_by_id(_self: object, _user_id: str) -> User:
        return user

    monkeypatch.setattr(UserRepository, "get_by_id", get_by_id)
    app = create_app()
    app.dependency_overrides[get_async_session] = fake_session
    app.dependency_overrides[asset_service] = lambda: service
    return TestClient(app), user


def auth_headers(user: User) -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token(str(user.id))}"}


def asset_payload() -> dict[str, str | None]:
    return {
        "symbol": "aapl",
        "name": " Apple Inc. ",
        "asset_type": "stock",
        "currency": "usd",
        "exchange": " nasdaq ",
        "isin": None,
    }


def test_list_assets_requires_auth(monkeypatch: MonkeyPatch) -> None:
    class StubService:
        async def list_assets(self) -> list[Asset]:
            return []

    client, _user = build_client(monkeypatch, service=StubService())  # type: ignore[arg-type]

    with client:
        response = client.get("/api/v1/assets")

    assert response.status_code == 401


def test_list_assets(monkeypatch: MonkeyPatch) -> None:
    asset = make_asset()

    class StubService:
        async def list_assets(self) -> list[Asset]:
            return [asset]

    client, user = build_client(monkeypatch, service=StubService())  # type: ignore[arg-type]

    with client:
        response = client.get("/api/v1/assets", headers=auth_headers(user))

    assert response.status_code == 200
    assert response.json()[0]["id"] == str(asset.id)
    assert response.json()[0]["symbol"] == "AAPL"


def test_create_asset_normalizes_and_forwards_payload(monkeypatch: MonkeyPatch) -> None:
    captured: dict[str, AssetCreate] = {}

    class StubService:
        async def create_asset(self, payload: AssetCreate) -> Asset:
            captured["payload"] = payload
            return make_asset(
                symbol=payload.symbol,
                name=payload.name,
                asset_type=payload.asset_type,
                currency=payload.currency,
                exchange=payload.exchange,
                isin=payload.isin,
            )

    client, user = build_client(monkeypatch, service=StubService())  # type: ignore[arg-type]

    with client:
        response = client.post(
            "/api/v1/assets",
            headers=auth_headers(user),
            json=asset_payload(),
        )

    assert response.status_code == 201
    assert response.json()["symbol"] == "AAPL"
    assert response.json()["currency"] == "USD"
    assert response.json()["exchange"] == "NASDAQ"
    request_payload = captured["payload"]
    assert request_payload.symbol == "AAPL"
    assert request_payload.name == "Apple Inc."


def test_create_asset_maps_conflict(monkeypatch: MonkeyPatch) -> None:
    class StubService:
        async def create_asset(self, _payload: AssetCreate) -> Asset:
            raise AssetAlreadyExistsError

    client, user = build_client(monkeypatch, service=StubService())  # type: ignore[arg-type]

    with client:
        response = client.post(
            "/api/v1/assets",
            headers=auth_headers(user),
            json=asset_payload(),
        )

    assert response.status_code == 409
    assert response.json()["detail"] == "Asset already exists"


def test_lookup_asset(monkeypatch: MonkeyPatch) -> None:
    asset = make_asset()

    class StubService:
        async def lookup_asset(self, symbol: str) -> Asset:
            assert symbol == "AAPL"
            return asset

    client, user = build_client(monkeypatch, service=StubService())  # type: ignore[arg-type]

    with client:
        response = client.post(
            "/api/v1/assets/lookup",
            headers=auth_headers(user),
            json={"symbol": "aapl"},
        )

    assert response.status_code == 200
    assert response.json()["id"] == str(asset.id)


def test_lookup_asset_maps_not_found(monkeypatch: MonkeyPatch) -> None:
    class StubService:
        async def lookup_asset(self, _symbol: str) -> Asset:
            raise AssetLookupNotFoundError

    client, user = build_client(monkeypatch, service=StubService())  # type: ignore[arg-type]

    with client:
        response = client.post(
            "/api/v1/assets/lookup",
            headers=auth_headers(user),
            json={"symbol": "unknown"},
        )

    assert response.status_code == 404
    assert response.json()["detail"] == "Asset symbol not found"


def test_lookup_asset_maps_unavailable(monkeypatch: MonkeyPatch) -> None:
    class StubService:
        async def lookup_asset(self, _symbol: str) -> Asset:
            raise AssetLookupUnavailableError

    client, user = build_client(monkeypatch, service=StubService())  # type: ignore[arg-type]

    with client:
        response = client.post(
            "/api/v1/assets/lookup",
            headers=auth_headers(user),
            json={"symbol": "aapl"},
        )

    assert response.status_code == 503
    assert response.json()["detail"] == "Asset lookup is temporarily unavailable"


def test_get_asset_maps_not_found(monkeypatch: MonkeyPatch) -> None:
    class StubService:
        async def get_asset(self, _asset_id: uuid.UUID) -> Asset:
            raise AssetNotFoundError

    client, user = build_client(monkeypatch, service=StubService())  # type: ignore[arg-type]

    with client:
        response = client.get(f"/api/v1/assets/{uuid.uuid4()}", headers=auth_headers(user))

    assert response.status_code == 404
    assert response.json()["detail"] == "Asset not found"
