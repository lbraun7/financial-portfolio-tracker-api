"""Asset service tests."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest
from app.core.exceptions import AssetAlreadyExistsError, AssetNotFoundError
from app.domain.enums import AssetType
from app.integrations.assets import AssetLookupResult
from app.models.asset import Asset
from app.schemas.asset import AssetCreate
from app.services.asset import AssetService


class FakeSession:
    pass


class AssetRepositoryStub:
    def __init__(
        self,
        existing: Asset | None = None,
        *,
        existing_identity: Asset | None = None,
        existing_isin: Asset | None = None,
    ) -> None:
        self.existing = existing
        self.existing_identity = existing_identity
        self.existing_isin = existing_isin
        self.created: Asset | None = None

    async def list(self) -> list[Asset]:
        return [self.existing] if self.existing is not None else []

    async def get_by_id(self, _asset_id: uuid.UUID) -> Asset | None:
        return self.existing

    async def get_by_identity(self, **_kwargs: object) -> Asset | None:
        return self.existing_identity

    async def get_by_isin(self, _isin: str) -> Asset | None:
        return self.existing_isin

    async def create(self, **kwargs: object) -> Asset:
        now = datetime.now(UTC)
        self.created = Asset(id=uuid.uuid4(), created_at=now, updated_at=now, **kwargs)
        return self.created


class AssetLookupProviderStub:
    async def lookup(self, _symbol: str) -> AssetLookupResult:
        return AssetLookupResult(
            symbol="AAPL",
            name="Apple Inc.",
            asset_type=AssetType.STOCK,
            currency="USD",
            exchange="UNITED STATES",
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


def payload(*, isin: str | None = None) -> AssetCreate:
    return AssetCreate(
        symbol="AAPL",
        name="Apple Inc.",
        asset_type=AssetType.STOCK,
        currency="USD",
        exchange="NASDAQ",
        isin=isin,
    )


def build_service(repository: AssetRepositoryStub) -> AssetService:
    service = AssetService(  # type: ignore[arg-type]
        FakeSession(),
        lookup_provider=AssetLookupProviderStub(),
    )
    service.repository = repository  # type: ignore[assignment]
    return service


async def test_get_asset_returns_existing_asset() -> None:
    asset = make_asset()
    service = build_service(AssetRepositoryStub(asset))

    assert await service.get_asset(asset.id) == asset


async def test_get_asset_raises_when_missing() -> None:
    service = build_service(AssetRepositoryStub())

    with pytest.raises(AssetNotFoundError):
        await service.get_asset(uuid.uuid4())


async def test_create_asset_persists_when_unique() -> None:
    repository = AssetRepositoryStub()
    service = build_service(repository)

    asset = await service.create_asset(payload())

    assert repository.created == asset
    assert asset.symbol == "AAPL"
    assert asset.exchange == "NASDAQ"


async def test_create_asset_rejects_duplicate_identity() -> None:
    service = build_service(AssetRepositoryStub(existing_identity=make_asset()))

    with pytest.raises(AssetAlreadyExistsError):
        await service.create_asset(payload())


async def test_create_asset_rejects_duplicate_isin() -> None:
    service = build_service(AssetRepositoryStub(existing_isin=make_asset()))

    with pytest.raises(AssetAlreadyExistsError):
        await service.create_asset(payload(isin="US0378331005"))


async def test_lookup_asset_returns_existing_asset() -> None:
    existing = make_asset(exchange="UNITED STATES")
    service = build_service(AssetRepositoryStub(existing_identity=existing))

    asset = await service.lookup_asset("aapl")

    assert asset == existing


async def test_lookup_asset_creates_when_missing() -> None:
    repository = AssetRepositoryStub()
    service = build_service(repository)

    asset = await service.lookup_asset("aapl")

    assert repository.created == asset
    assert asset.symbol == "AAPL"
    assert asset.name == "Apple Inc."
    assert asset.exchange == "UNITED STATES"
