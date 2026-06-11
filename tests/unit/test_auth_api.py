"""Authentication endpoint tests."""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime

from app.core.security import create_access_token, create_refresh_token, hash_password
from app.db.session import get_async_session
from app.main import create_app
from app.models.user import User
from app.repositories.users import UserRepository
from fastapi.testclient import TestClient
from pytest import MonkeyPatch

RAW_PASSWORD = "correct-password"


async def fake_session() -> AsyncIterator[object]:
    yield object()


def make_user(
    *,
    user_id: uuid.UUID | None = None,
    email: str = "ada@example.com",
    raw_password: str = RAW_PASSWORD,
    is_active: bool = True,
) -> User:
    user = User(
        id=user_id or uuid.uuid4(),
        email=email,
        hashed_password=hash_password(raw_password),
        full_name="Ada Lovelace",
        is_active=is_active,
        created_at=datetime.now(UTC),
    )
    return user


def test_register_creates_user(monkeypatch: MonkeyPatch) -> None:
    created_user = make_user(email="new@example.com")
    captured: dict[str, str | None] = {}

    async def get_by_email(_self: object, email: str) -> User | None:
        captured["lookup_email"] = email
        return None

    async def create(
        _self: object,
        *,
        email: str,
        hashed_password: str,
        full_name: str | None,
    ) -> User:
        captured["created_email"] = email
        captured["created_full_name"] = full_name
        captured["created_hash"] = hashed_password
        return created_user

    monkeypatch.setattr(UserRepository, "get_by_email", get_by_email)
    monkeypatch.setattr(UserRepository, "create", create)

    app = create_app()
    app.dependency_overrides[get_async_session] = fake_session

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/auth/register",
            json={
                "email": " New@Example.com ",
                "password": RAW_PASSWORD,
                "full_name": " Ada Lovelace ",
            },
        )

    assert response.status_code == 201
    assert response.json()["email"] == "new@example.com"
    assert captured["lookup_email"] == "new@example.com"
    assert captured["created_email"] == "new@example.com"
    assert captured["created_full_name"] == "Ada Lovelace"
    assert captured["created_hash"] != RAW_PASSWORD


def test_register_rejects_existing_email(monkeypatch: MonkeyPatch) -> None:
    async def get_by_email(_self: object, _email: str) -> User | None:
        return make_user()

    monkeypatch.setattr(UserRepository, "get_by_email", get_by_email)

    app = create_app()
    app.dependency_overrides[get_async_session] = fake_session

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/auth/register",
            json={"email": "ada@example.com", "password": RAW_PASSWORD},
        )

    assert response.status_code == 409


def test_login_issues_token_pair(monkeypatch: MonkeyPatch) -> None:
    user = make_user(raw_password=RAW_PASSWORD)

    async def get_by_email(_self: object, _email: str) -> User | None:
        return user

    monkeypatch.setattr(UserRepository, "get_by_email", get_by_email)

    app = create_app()
    app.dependency_overrides[get_async_session] = fake_session

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/auth/login",
            json={"email": "ada@example.com", "password": RAW_PASSWORD},
        )

    body = response.json()
    assert response.status_code == 200
    assert body["token_type"] == "bearer"
    assert body["access_token"]
    assert body["refresh_token"]


def test_login_rejects_bad_password(monkeypatch: MonkeyPatch) -> None:
    user = make_user(raw_password=RAW_PASSWORD)

    async def get_by_email(_self: object, _email: str) -> User | None:
        return user

    monkeypatch.setattr(UserRepository, "get_by_email", get_by_email)

    app = create_app()
    app.dependency_overrides[get_async_session] = fake_session

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/auth/login",
            json={"email": "ada@example.com", "password": "wrong-password"},
        )

    assert response.status_code == 401


def test_refresh_issues_new_token_pair(monkeypatch: MonkeyPatch) -> None:
    user_id = uuid.uuid4()
    user = make_user(user_id=user_id)

    async def get_by_id(_self: object, token_user_id: str) -> User | None:
        assert token_user_id == str(user_id)
        return user

    monkeypatch.setattr(UserRepository, "get_by_id", get_by_id)

    app = create_app()
    app.dependency_overrides[get_async_session] = fake_session

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": create_refresh_token(str(user_id))},
        )

    assert response.status_code == 200
    assert response.json()["access_token"]
    assert response.json()["refresh_token"]


def test_me_returns_current_user(monkeypatch: MonkeyPatch) -> None:
    user_id = uuid.uuid4()
    user = make_user(user_id=user_id)

    async def get_by_id(_self: object, _token_user_id: str) -> User | None:
        return user

    monkeypatch.setattr(UserRepository, "get_by_id", get_by_id)

    app = create_app()
    app.dependency_overrides[get_async_session] = fake_session

    with TestClient(app) as client:
        response = client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {create_access_token(str(user_id))}"},
        )

    assert response.status_code == 200
    assert response.json()["email"] == "ada@example.com"
