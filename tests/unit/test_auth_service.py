"""Authentication service tests."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest
from app.core.exceptions import (
    EmailAlreadyRegisteredError,
    InactiveUserError,
    InvalidAccessTokenError,
    InvalidCredentialsError,
    InvalidRefreshTokenError,
)
from app.core.security import create_access_token, create_refresh_token, hash_password
from app.models.user import User
from app.schemas.auth import UserCreate
from app.services.auth import AuthService

RAW_PASSWORD = "correct-password"


def make_user(
    *,
    user_id: uuid.UUID | None = None,
    email: str = "ada@example.com",
    raw_password: str = RAW_PASSWORD,
    is_active: bool = True,
) -> User:
    return User(
        id=user_id or uuid.uuid4(),
        email=email,
        hashed_password=hash_password(raw_password),
        full_name="Ada Lovelace",
        is_active=is_active,
        created_at=datetime.now(UTC),
    )


class UserRepositoryStub:
    def __init__(self, users: list[User] | None = None) -> None:
        self.users = users or []
        self.created: dict[str, str | None] | None = None

    async def get_by_email(self, email: str) -> User | None:
        return next((user for user in self.users if user.email == email), None)

    async def get_by_id(self, user_id: str) -> User | None:
        return next((user for user in self.users if str(user.id) == user_id), None)

    async def create(
        self,
        *,
        email: str,
        hashed_password: str,
        full_name: str | None,
    ) -> User:
        self.created = {
            "email": email,
            "hashed_password": hashed_password,
            "full_name": full_name,
        }
        user = make_user(email=email)
        user.hashed_password = hashed_password
        user.full_name = full_name
        self.users.append(user)
        return user


def make_service(repository: UserRepositoryStub) -> AuthService:
    service = AuthService(object())  # type: ignore[arg-type]
    service.users = repository  # type: ignore[assignment]
    return service


async def test_register_user_rejects_duplicate_and_hashes_password() -> None:
    repository = UserRepositoryStub([make_user()])
    service = make_service(repository)

    with pytest.raises(EmailAlreadyRegisteredError):
        await service.register_user(
            UserCreate(email="ada@example.com", password=RAW_PASSWORD),
        )

    created = await service.register_user(
        UserCreate(
            email="grace@example.com",
            password=RAW_PASSWORD,
            full_name="Grace Hopper",
        ),
    )

    assert created.email == "grace@example.com"
    assert repository.created is not None
    assert repository.created["hashed_password"] != RAW_PASSWORD
    assert repository.created["full_name"] == "Grace Hopper"


async def test_authenticate_user_issues_tokens_and_rejects_invalid_login() -> None:
    user = make_user(raw_password=RAW_PASSWORD)
    service = make_service(UserRepositoryStub([user]))

    token_pair = await service.authenticate_user(email=user.email, password=RAW_PASSWORD)

    assert token_pair.token_type == "bearer"
    assert token_pair.access_token
    assert token_pair.refresh_token

    with pytest.raises(InvalidCredentialsError):
        await service.authenticate_user(email=user.email, password="wrong-password")

    inactive = make_user(email="inactive@example.com", is_active=False)
    service = make_service(UserRepositoryStub([inactive]))

    with pytest.raises(InactiveUserError):
        await service.authenticate_user(email=inactive.email, password=RAW_PASSWORD)


async def test_refresh_tokens_resolves_active_user() -> None:
    user_id = uuid.uuid4()
    user = make_user(user_id=user_id)
    service = make_service(UserRepositoryStub([user]))

    token_pair = await service.refresh_tokens(create_refresh_token(str(user_id)))

    assert token_pair.access_token
    assert token_pair.refresh_token

    with pytest.raises(InvalidRefreshTokenError):
        await service.refresh_tokens("not-a-token")

    inactive_user = make_user(user_id=uuid.uuid4(), email="inactive@example.com", is_active=False)
    service = make_service(UserRepositoryStub([inactive_user]))

    with pytest.raises(InvalidRefreshTokenError):
        await service.refresh_tokens(create_refresh_token(str(inactive_user.id)))


async def test_get_user_from_access_token_resolves_active_user() -> None:
    user_id = uuid.uuid4()
    user = make_user(user_id=user_id)
    service = make_service(UserRepositoryStub([user]))

    assert await service.get_user_from_access_token(create_access_token(str(user_id))) is user

    with pytest.raises(InvalidAccessTokenError):
        await service.get_user_from_access_token("not-a-token")

    inactive_user = make_user(user_id=uuid.uuid4(), email="inactive@example.com", is_active=False)
    service = make_service(UserRepositoryStub([inactive_user]))

    with pytest.raises(InvalidAccessTokenError):
        await service.get_user_from_access_token(create_access_token(str(inactive_user.id)))
