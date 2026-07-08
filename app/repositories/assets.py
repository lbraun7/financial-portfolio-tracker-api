"""Asset repository."""

from __future__ import annotations

import uuid
from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.enums import AssetType
from app.models.asset import Asset


class AssetRepository:
    """Persistence operations for assets."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list(self) -> Sequence[Asset]:
        """Return all assets ordered by symbol."""

        result = await self.session.execute(
            select(Asset).order_by(Asset.symbol, Asset.exchange, Asset.currency)
        )
        return result.scalars().all()

    async def get_by_id(self, asset_id: uuid.UUID) -> Asset | None:
        result = await self.session.execute(select(Asset).where(Asset.id == asset_id))
        return result.scalar_one_or_none()

    async def get_by_identity(
        self,
        *,
        symbol: str,
        exchange: str | None,
        currency: str,
    ) -> Asset | None:
        """Return an asset by its natural unique key."""

        result = await self.session.execute(
            select(Asset).where(
                Asset.symbol == symbol,
                Asset.exchange == exchange,
                Asset.currency == currency,
            )
        )
        return result.scalar_one_or_none()

    async def get_by_isin(self, isin: str) -> Asset | None:
        """Return an asset by ISIN."""

        result = await self.session.execute(select(Asset).where(Asset.isin == isin))
        return result.scalar_one_or_none()

    async def create(
        self,
        *,
        symbol: str,
        name: str,
        asset_type: AssetType,
        currency: str,
        exchange: str | None,
        isin: str | None,
    ) -> Asset:
        """Create and persist an asset."""

        asset = Asset(
            symbol=symbol,
            name=name,
            asset_type=asset_type,
            currency=currency,
            exchange=exchange,
            isin=isin,
        )
        self.session.add(asset)
        await self.session.commit()
        await self.session.refresh(asset)
        return asset
