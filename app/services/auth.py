"""Authentication use cases."""

from __future__ import annotations

import jwt
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import (
    EmailAlreadyRegisteredError,
    InactiveUserError,
    InvalidAccessTokenError,
    InvalidCredentialsError,
    InvalidRefreshTokenError,
)
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.models.user import User
from app.repositories.users import UserRepository
from app.schemas.auth import TokenPair, UserCreate


class AuthService:
    """Authentication use cases for users and JWT tokens."""

    def __init__(self, session: AsyncSession) -> None:
        self.users = UserRepository(session)

    async def register_user(self, payload: UserCreate) -> User:
        """Register a new user account."""

        existing_user = await self.users.get_by_email(payload.email)
        if existing_user is not None:
            raise EmailAlreadyRegisteredError

        return await self.users.create(
            email=payload.email,
            hashed_password=hash_password(payload.password),
            full_name=payload.full_name,
        )

    async def authenticate_user(self, *, email: str, password: str) -> TokenPair:
        """Authenticate a user and issue tokens."""

        user = await self.users.get_by_email(email)
        if user is None or not verify_password(password, user.hashed_password):
            raise InvalidCredentialsError
        if not user.is_active:
            raise InactiveUserError

        return self.build_token_pair(user)

    async def refresh_tokens(self, refresh_token: str) -> TokenPair:
        """Exchange a refresh token for a new token pair."""

        try:
            user_id = decode_token(refresh_token, expected_type="refresh")
        except jwt.PyJWTError as exc:
            raise InvalidRefreshTokenError from exc

        user = await self.users.get_by_id(user_id)
        if user is None or not user.is_active:
            raise InvalidRefreshTokenError

        return self.build_token_pair(user)

    async def get_user_from_access_token(self, access_token: str) -> User:
        """Resolve an active user from an access token."""

        try:
            user_id = decode_token(access_token, expected_type="access")
        except jwt.PyJWTError as exc:
            raise InvalidAccessTokenError from exc

        user = await self.users.get_by_id(user_id)
        if user is None or not user.is_active:
            raise InvalidAccessTokenError

        return user

    def build_token_pair(self, user: User) -> TokenPair:
        """Return a new access/refresh pair for a user."""

        subject = str(user.id)
        return TokenPair(
            access_token=create_access_token(subject),
            refresh_token=create_refresh_token(subject),
        )
