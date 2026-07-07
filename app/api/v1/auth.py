"""Authentication endpoints."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import (
    EmailAlreadyRegisteredError,
    InactiveUserError,
    InvalidAccessTokenError,
    InvalidCredentialsError,
    InvalidRefreshTokenError,
)
from app.core.rate_limit import enforce_auth_rate_limit
from app.db.session import get_async_session
from app.models.user import User
from app.schemas.auth import RefreshTokenRequest, TokenPair, UserCreate, UserLogin, UserRead
from app.services.auth import AuthService

router = APIRouter(prefix="/auth", tags=["auth"])
bearer_scheme = HTTPBearer(auto_error=False)


def auth_service(
    session: Annotated[AsyncSession, Depends(get_async_session)],
) -> AuthService:
    """Build the authentication service dependency."""

    return AuthService(session)


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
    service: Annotated[AuthService, Depends(auth_service)],
) -> User:
    """Resolve the current active user from an access token."""

    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing bearer token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        return await service.get_user_from_access_token(credentials.credentials)
    except InvalidAccessTokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid access token",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc


@router.post(
    "/register",
    response_model=UserRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(enforce_auth_rate_limit)],
)
async def register(
    payload: UserCreate,
    service: Annotated[AuthService, Depends(auth_service)],
) -> User:
    """Register a new user account."""

    try:
        return await service.register_user(payload)
    except EmailAlreadyRegisteredError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email is already registered",
        ) from exc


@router.post(
    "/login",
    response_model=TokenPair,
    dependencies=[Depends(enforce_auth_rate_limit)],
)
async def login(
    payload: UserLogin,
    service: Annotated[AuthService, Depends(auth_service)],
) -> TokenPair:
    """Authenticate a user and issue tokens."""

    try:
        return await service.authenticate_user(email=payload.email, password=payload.password)
    except InvalidCredentialsError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc
    except InactiveUserError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is inactive",
        ) from exc


@router.post(
    "/refresh",
    response_model=TokenPair,
    dependencies=[Depends(enforce_auth_rate_limit)],
)
async def refresh(
    payload: RefreshTokenRequest,
    service: Annotated[AuthService, Depends(auth_service)],
) -> TokenPair:
    """Exchange a refresh token for a new token pair."""

    try:
        return await service.refresh_tokens(payload.refresh_token)
    except InvalidRefreshTokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc


@router.get("/me", response_model=UserRead)
async def read_current_user(
    current_user: Annotated[User, Depends(get_current_user)],
) -> User:
    """Return the current user."""

    return current_user
