"""Authentication and password security helpers."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Literal

import bcrypt
import jwt

from app.core.config import settings

TokenType = Literal["access", "refresh"]


def hash_password(password: str) -> str:
    """Return a bcrypt hash for a plain text password."""

    password_bytes = password.encode("utf-8")
    return bcrypt.hashpw(password_bytes, bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, hashed_password: str) -> bool:
    """Return whether a plain text password matches a bcrypt hash."""

    password_bytes = password.encode("utf-8")
    hashed_password_bytes = hashed_password.encode("utf-8")
    return bcrypt.checkpw(password_bytes, hashed_password_bytes)


def create_token(subject: str, token_type: TokenType, expires_delta: timedelta) -> str:
    """Create a signed JWT for a subject."""

    expires_at = datetime.now(UTC) + expires_delta
    payload: dict[str, object] = {
        "sub": subject,
        "type": token_type,
        "exp": expires_at,
        "iat": datetime.now(UTC),
    }
    return jwt.encode(payload, settings.secret_key, algorithm=settings.algorithm)


def create_access_token(subject: str) -> str:
    """Create a short-lived access token."""

    return create_token(
        subject=subject,
        token_type="access",
        expires_delta=timedelta(minutes=settings.access_token_expire_minutes),
    )


def create_refresh_token(subject: str) -> str:
    """Create a longer-lived refresh token."""

    return create_token(
        subject=subject,
        token_type="refresh",
        expires_delta=timedelta(days=settings.refresh_token_expire_days),
    )


def decode_token(token: str, expected_type: TokenType) -> str:
    """Decode a JWT and return its subject when the token type matches."""

    payload = jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
    subject = payload.get("sub")
    token_type = payload.get("type")
    if not isinstance(subject, str) or token_type != expected_type:
        raise jwt.InvalidTokenError("Invalid token payload")
    return subject
