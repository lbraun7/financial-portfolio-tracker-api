"""Transaction endpoints."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.assets import asset_service as asset_lookup_service
from app.api.v1.auth import get_current_user
from app.core.exceptions import (
    AssetCurrencyMismatchError,
    AssetLookupNotFoundError,
    AssetLookupUnavailableError,
    AssetNotFoundError,
    IdempotencyConflictError,
    InsufficientPositionError,
    OutOfOrderTransactionError,
    PortfolioNotFoundError,
)
from app.db.session import get_async_session
from app.models.transaction import Transaction
from app.models.user import User
from app.schemas.transaction import TransactionCreate, TransactionRead
from app.services.asset import AssetService
from app.services.transaction import TransactionService

router = APIRouter(prefix="/portfolios/{portfolio_id}/transactions", tags=["transactions"])


def transaction_service(
    session: Annotated[AsyncSession, Depends(get_async_session)],
) -> TransactionService:
    """Build the transaction engine dependency."""

    return TransactionService(session)


@router.get("", response_model=list[TransactionRead])
async def list_transactions(
    portfolio_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    service: Annotated[TransactionService, Depends(transaction_service)],
) -> list[Transaction]:
    try:
        return list(
            await service.list_transactions(
                portfolio_id=portfolio_id,
                user_id=current_user.id,
            )
        )
    except PortfolioNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Portfolio not found") from exc


@router.post("", response_model=TransactionRead, status_code=status.HTTP_201_CREATED)
async def record_transaction(
    portfolio_id: uuid.UUID,
    payload: TransactionCreate,
    current_user: Annotated[User, Depends(get_current_user)],
    service: Annotated[TransactionService, Depends(transaction_service)],
    assets: Annotated[AssetService, Depends(asset_lookup_service)],
    idempotency_key: Annotated[
        str,
        Header(alias="Idempotency-Key", min_length=1, max_length=128),
    ],
) -> Transaction:
    normalized_key = idempotency_key.strip()
    if not normalized_key:
        raise HTTPException(status_code=422, detail="Idempotency-Key must not be blank")

    if payload.asset_id is None and payload.symbol is not None:
        try:
            asset = await assets.lookup_asset(payload.symbol)
        except AssetLookupNotFoundError as exc:
            raise HTTPException(status_code=404, detail="Asset symbol not found") from exc
        except AssetLookupUnavailableError as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Asset lookup is temporarily unavailable",
            ) from exc
        payload = payload.model_copy(update={"asset_id": asset.id, "symbol": None})

    try:
        return await service.record(
            portfolio_id=portfolio_id,
            user_id=current_user.id,
            payload=payload,
            idempotency_key=normalized_key,
        )
    except PortfolioNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Portfolio not found") from exc
    except AssetNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Asset not found") from exc
    except AssetCurrencyMismatchError as exc:
        raise HTTPException(
            status_code=422,
            detail="Transaction currency must match asset currency",
        ) from exc
    except InsufficientPositionError as exc:
        raise HTTPException(
            status_code=409,
            detail="Insufficient position quantity for sell",
        ) from exc
    except IdempotencyConflictError as exc:
        raise HTTPException(
            status_code=409,
            detail="Idempotency-Key was already used with a different payload",
        ) from exc
    except OutOfOrderTransactionError as exc:
        raise HTTPException(
            status_code=409,
            detail="Transaction trade_date predates the latest transaction for this asset",
        ) from exc
