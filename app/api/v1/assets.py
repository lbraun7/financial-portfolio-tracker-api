"""Asset endpoints."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.auth import get_current_user
from app.core.config import settings
from app.core.exceptions import (
    AssetAlreadyExistsError,
    AssetLookupNotFoundError,
    AssetLookupUnavailableError,
    AssetNotFoundError,
)
from app.db.session import get_async_session
from app.integrations.assets import AlphaVantageAssetLookupProvider
from app.models.asset import Asset
from app.models.user import User
from app.schemas.asset import AssetCreate, AssetLookup, AssetRead
from app.services.asset import AssetService

router = APIRouter(prefix="/assets", tags=["assets"])


def asset_service(
    session: Annotated[AsyncSession, Depends(get_async_session)],
) -> AssetService:
    """Build the asset service dependency."""

    provider = AlphaVantageAssetLookupProvider(
        api_key=settings.price_api_key,
        base_url=settings.price_api_base_url,
        timeout_seconds=settings.price_request_timeout_seconds,
    )
    return AssetService(session, lookup_provider=provider)


@router.get("", response_model=list[AssetRead])
async def list_assets(
    _current_user: Annotated[User, Depends(get_current_user)],
    service: Annotated[AssetService, Depends(asset_service)],
) -> list[Asset]:
    """List known assets."""

    return list(await service.list_assets())


@router.post("", response_model=AssetRead, status_code=status.HTTP_201_CREATED)
async def create_asset(
    payload: AssetCreate,
    _current_user: Annotated[User, Depends(get_current_user)],
    service: Annotated[AssetService, Depends(asset_service)],
) -> Asset:
    """Create an asset."""

    try:
        return await service.create_asset(payload)
    except AssetAlreadyExistsError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Asset already exists",
        ) from exc


@router.post("/lookup", response_model=AssetRead)
async def lookup_asset(
    payload: AssetLookup,
    _current_user: Annotated[User, Depends(get_current_user)],
    service: Annotated[AssetService, Depends(asset_service)],
) -> Asset:
    """Look up a symbol externally and create the asset when needed."""

    try:
        return await service.lookup_asset(payload.symbol)
    except AssetLookupNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Asset symbol not found") from exc
    except AssetLookupUnavailableError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Asset lookup is temporarily unavailable",
        ) from exc


@router.get("/{asset_id}", response_model=AssetRead)
async def get_asset(
    asset_id: uuid.UUID,
    _current_user: Annotated[User, Depends(get_current_user)],
    service: Annotated[AssetService, Depends(asset_service)],
) -> Asset:
    """Return an asset by ID."""

    try:
        return await service.get_asset(asset_id)
    except AssetNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Asset not found") from exc
