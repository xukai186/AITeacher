from datetime import timedelta

import pytest

from app.auth.security import (
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)


def test_hash_and_verify_password_roundtrip():
    hashed = hash_password("hunter2")
    assert hashed != "hunter2"
    assert verify_password("hunter2", hashed) is True
    assert verify_password("wrong", hashed) is False


def test_jwt_roundtrip_carries_claims():
    token = create_access_token({"sub": "user-123", "role": "org_admin"})
    payload = decode_access_token(token)
    assert payload["sub"] == "user-123"
    assert payload["role"] == "org_admin"


def test_expired_token_rejected():
    token = create_access_token({"sub": "x"}, expires_delta=timedelta(seconds=-1))
    with pytest.raises(ValueError):
        decode_access_token(token)
