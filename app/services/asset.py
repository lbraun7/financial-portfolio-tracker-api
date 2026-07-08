"""Asset use cases."""

from __future__ import annotations

import uuid
from collections.abc import Sequence

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import (
    AssetAlreadyExistsError,
    AssetLookupUnavailableError,
    AssetNotFoundError,
)
from app.integrations.assets import AssetLookupProvider
from app.models.asset import Asset
from app.repositories.assets import AssetRepository
from app.schemas.asset import AssetCreate


class AssetService:
    """Asset use cases."""

    def __init__(
        self,
        session: AsyncSession,
        *,
        lookup_provider: AssetLookupProvider | None = None,
    ) -> None:
        self.repository = AssetRepository(session)
        self.lookup_provider = lookup_provider

    async def list_assets(self) -> Sequence[Asset]:
        """List known tradable assets."""

        return await self.repository.list()

    async def get_asset(self, asset_id: uuid.UUID) -> Asset:
        """Return one asset by ID."""

        asset = await self.repository.get_by_id(asset_id)
        if asset is None:
            raise AssetNotFoundError
        return asset

    async def create_asset(self, payload: AssetCreate) -> Asset:
        """Create an asset when its unique identifiers are unused."""

        existing = await self.repository.get_by_identity(
            symbol=payload.symbol,
            exchange=payload.exchange,
            currency=payload.currency,
        )
        if existing is not None:
            raise AssetAlreadyExistsError

        if payload.isin is not None:
            existing = await self.repository.get_by_isin(payload.isin)
            if existing is not None:
                raise AssetAlreadyExistsError

        return await self.repository.create(
            symbol=payload.symbol,
            name=payload.name,
            asset_type=payload.asset_type,
            currency=payload.currency,
            exchange=payload.exchange,
            isin=payload.isin,
        )

    async def lookup_asset(self, symbol: str) -> Asset:
        """Look up a symbol externally and return an existing or newly created asset."""

        if self.lookup_provider is None:
            raise AssetLookupUnavailableError("Asset lookup provider is not configured")

        metadata = await self.lookup_provider.lookup(symbol)
        existing = await self.repository.get_by_identity(
            symbol=metadata.symbol,
            exchange=metadata.exchange,
            currency=metadata.currency,
        )
        if existing is not None:
            return existing

        if metadata.isin is not None:
            existing = await self.repository.get_by_isin(metadata.isin)
            if existing is not None:
                return existing

        return await self.repository.create(
            symbol=metadata.symbol,
            name=metadata.name,
            asset_type=metadata.asset_type,
            currency=metadata.currency,
            exchange=metadata.exchange,
            isin=metadata.isin,
        )
