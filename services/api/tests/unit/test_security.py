"""Tests for security functions."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from app.core.security import create_access_token, decode_token, hash_password, verify_password


def test_password_hashing_roundtrip():
    password = "SecurePass123!"
    hashed = hash_password(password)
    assert hashed != password
    assert verify_password(password, hashed)


def test_wrong_password_rejected():
    hashed = hash_password("CorrectPass123!")
    assert not verify_password("WrongPass456!", hashed)


def test_token_creation_and_decoding():
    token = create_access_token({"sub": "test-user", "role": "officer"})
    payload = decode_token(token)
    assert payload["sub"] == "test-user"
    assert payload["role"] == "officer"


def test_invalid_token_rejected():
    try:
        decode_token("invalid.token.value")
        assert False, "Should have raised"
    except Exception as e:
        # Should raise HTTPException
        assert hasattr(e, "status_code")
