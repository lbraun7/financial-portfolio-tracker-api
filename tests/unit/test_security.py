"""Security helper tests."""

import jwt
import pytest
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)


def test_hash_password_uses_bcrypt_and_verifies_password() -> None:
    hashed_password = hash_password("correct horse battery staple")

    assert hashed_password != "correct horse battery staple"
    assert hashed_password.startswith("$2")
    assert verify_password("correct horse battery staple", hashed_password) is True
    assert verify_password("wrong password", hashed_password) is False


def test_decode_token_returns_subject_for_expected_type() -> None:
    token = create_access_token("user-id")

    assert decode_token(token, expected_type="access") == "user-id"


def test_decode_token_rejects_wrong_token_type() -> None:
    token = create_refresh_token("user-id")

    with pytest.raises(jwt.InvalidTokenError):
        decode_token(token, expected_type="access")
