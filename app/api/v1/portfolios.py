"""Portfolio endpoints."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.auth import get_current_user
from app.db.session import get_async_session
from app.models.portfolio import Portfolio
from app.models.user import User
from app.schemas.portfolio import PortfolioCreate, PortfolioRead, PortfolioUpdate
from app.services.portfolio import (
    PortfolioNameAlreadyExistsError,
    PortfolioNotFoundError,
    PortfolioService,
)

router = APIRouter(prefix="/portfolios", tags=["portfolios"])


def portfolio_service(
    session: Annotated[AsyncSession, Depends(get_async_session)],
) -> PortfolioService:
    """Build the portfolio service dependency."""

    return PortfolioService(session)


@router.get("", response_model=list[PortfolioRead])
async def list_portfolios(
    current_user: Annotated[User, Depends(get_current_user)],
    service: Annotated[PortfolioService, Depends(portfolio_service)],
) -> list[Portfolio]:
    """List portfolios owned by the current user."""

    return list(await service.list_portfolios(current_user.id))


@router.post("", response_model=PortfolioRead, status_code=status.HTTP_201_CREATED)
async def create_portfolio(
    payload: PortfolioCreate,
    current_user: Annotated[User, Depends(get_current_user)],
    service: Annotated[PortfolioService, Depends(portfolio_service)],
) -> Portfolio:
    """Create a portfolio for the current user."""

    try:
        return await service.create_portfolio(payload=payload, user_id=current_user.id)
    except PortfolioNameAlreadyExistsError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Portfolio name already exists",
        ) from exc


@router.get("/{portfolio_id}", response_model=PortfolioRead)
async def get_portfolio(
    portfolio_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    service: Annotated[PortfolioService, Depends(portfolio_service)],
) -> Portfolio:
    """Return a portfolio owned by the current user."""

    try:
        return await service.get_portfolio(portfolio_id=portfolio_id, user_id=current_user.id)
    except PortfolioNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Portfolio not found",
        ) from exc


@router.patch("/{portfolio_id}", response_model=PortfolioRead)
async def update_portfolio(
    portfolio_id: uuid.UUID,
    payload: PortfolioUpdate,
    current_user: Annotated[User, Depends(get_current_user)],
    service: Annotated[PortfolioService, Depends(portfolio_service)],
) -> Portfolio:
    """Partially update a portfolio owned by the current user."""

    try:
        return await service.update_portfolio(
            portfolio_id=portfolio_id,
            payload=payload,
            user_id=current_user.id,
        )
    except PortfolioNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Portfolio not found",
        ) from exc
    except PortfolioNameAlreadyExistsError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Portfolio name already exists",
        ) from exc


@router.delete("/{portfolio_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_portfolio(
    portfolio_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    service: Annotated[PortfolioService, Depends(portfolio_service)],
) -> Response:
    """Delete a portfolio owned by the current user."""

    try:
        await service.delete_portfolio(portfolio_id=portfolio_id, user_id=current_user.id)
    except PortfolioNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Portfolio not found",
        ) from exc

    return Response(status_code=status.HTTP_204_NO_CONTENT)
