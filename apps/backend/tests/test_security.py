"""Auth primitives: password hashing, JWT lifecycle, refresh token pairs."""

import pytest
from fastapi import HTTPException
from jose import jwt

from app.core.config import settings
from app.core.security import (
    create_access_token,
    create_refresh_token_pair,
    decode_access_token,
    hash_password,
    hash_token,
    verify_password,
)


def test_password_hash_roundtrip():
    hashed = hash_password("correct horse battery staple")
    assert hashed != "correct horse battery staple"
    assert verify_password("correct horse battery staple", hashed)
    assert not verify_password("wrong password", hashed)


def test_access_token_roundtrip():
    token = create_access_token("user-123", "creator")
    payload = decode_access_token(token)
    assert payload["sub"] == "user-123"
    assert payload["role"] == "creator"
    assert payload["type"] == "access"


def test_decode_rejects_garbage():
    with pytest.raises(HTTPException) as exc:
        decode_access_token("not-a-jwt")
    assert exc.value.status_code == 401


def test_decode_rejects_wrong_token_type():
    forged = jwt.encode(
        {"sub": "user-123", "type": "refresh"}, settings.SECRET_KEY, algorithm=settings.JWT_ALGORITHM
    )
    with pytest.raises(HTTPException):
        decode_access_token(forged)


def test_decode_rejects_wrong_signature():
    forged = jwt.encode(
        {"sub": "user-123", "type": "access"}, "attacker-key", algorithm=settings.JWT_ALGORITHM
    )
    with pytest.raises(HTTPException):
        decode_access_token(forged)


def test_refresh_pair_only_hash_is_stored():
    raw, hashed = create_refresh_token_pair()
    assert raw != hashed
    assert hash_token(raw) == hashed
