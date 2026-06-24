"""Position query endpoints."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from app.api.v1.auth import get_current_user
from app.api.v1.transactions import transaction_service
from app.core.exceptions import PortfolioNotFoundError
from app.models.position import Position
from app.models.user import User
from app.schemas.position import PositionRead
from app.services.transaction import TransactionService

router = APIRouter(prefix="/portfolios/{portfolio_id}/positions", tags=["positions"])


@router.get("", response_model=list[PositionRead])
async def list_positions(
    portfolio_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    service: Annotated[TransactionService, Depends(transaction_service)],
) -> list[Position]:
    try:
        return list(
            await service.list_positions(
                portfolio_id=portfolio_id,
                user_id=current_user.id,
            )
        )
    except PortfolioNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Portfolio not found") from exc
