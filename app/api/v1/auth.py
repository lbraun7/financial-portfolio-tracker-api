"""Authentication endpoints."""

from __future__ import annotations

from typing import Annotated

import jwt
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.rate_limit import enforce_auth_rate_limit
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.db.session import get_async_session
from app.models.user import User
from app.repositories.users import UserRepository
from app.schemas.auth import RefreshTokenRequest, TokenPair, UserCreate, UserLogin, UserRead

router = APIRouter(prefix="/auth", tags=["auth"])
bearer_scheme = HTTPBearer(auto_error=False)


def build_token_pair(user: User) -> TokenPair:
    """Return a new access/refresh pair for a user."""

    subject = str(user.id)
    return TokenPair(
        access_token=create_access_token(subject),
        refresh_token=create_refresh_token(subject),
    )


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
    session: Annotated[AsyncSession, Depends(get_async_session)],
) -> User:
    """Resolve the current active user from an access token."""

    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing bearer token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        user_id = decode_token(credentials.credentials, expected_type="access")
    except jwt.PyJWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid access token",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    user = await UserRepository(session).get_by_id(user_id)
    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid access token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


@router.post(
    "/register",
    response_model=UserRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(enforce_auth_rate_limit)],
)
async def register(
    payload: UserCreate,
    session: Annotated[AsyncSession, Depends(get_async_session)],
) -> User:
    """Register a new user account."""

    repository = UserRepository(session)
    existing_user = await repository.get_by_email(payload.email)
    if existing_user is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email is already registered",
        )

    return await repository.create(
        email=payload.email,
        hashed_password=hash_password(payload.password),
        full_name=payload.full_name,
    )


@router.post(
    "/login",
    response_model=TokenPair,
    dependencies=[Depends(enforce_auth_rate_limit)],
)
async def login(
    payload: UserLogin,
    session: Annotated[AsyncSession, Depends(get_async_session)],
) -> TokenPair:
    """Authenticate a user and issue tokens."""

    user = await UserRepository(session).get_by_email(payload.email)
    if user is None or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is inactive",
        )

    return build_token_pair(user)


@router.post(
    "/refresh",
    response_model=TokenPair,
    dependencies=[Depends(enforce_auth_rate_limit)],
)
async def refresh(
    payload: RefreshTokenRequest,
    session: Annotated[AsyncSession, Depends(get_async_session)],
) -> TokenPair:
    """Exchange a refresh token for a new token pair."""

    try:
        user_id = decode_token(payload.refresh_token, expected_type="refresh")
    except jwt.PyJWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    user = await UserRepository(session).get_by_id(user_id)
    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return build_token_pair(user)


@router.get("/me", response_model=UserRead)
async def read_current_user(
    current_user: Annotated[User, Depends(get_current_user)],
) -> User:
    """Return the current user."""

    return current_user
