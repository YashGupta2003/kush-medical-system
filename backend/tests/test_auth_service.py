"""Tests for auth_service.py - password hashing and JWT tokens."""
from app.services.auth_service import (
    hash_password, verify_password, create_access_token, decode_access_token,
)
from app import models


def test_password_hash_is_not_plaintext():
    hashed = hash_password("mySecret123")
    assert hashed != "mySecret123"
    assert len(hashed) > 20


def test_correct_password_verifies():
    hashed = hash_password("mySecret123")
    assert verify_password("mySecret123", hashed) is True


def test_wrong_password_fails_verification():
    hashed = hash_password("mySecret123")
    assert verify_password("wrongPassword", hashed) is False


def test_same_password_hashes_differently_each_time():
    """bcrypt salts every hash, so hashing the same password twice must
    never produce identical hashes - this is a basic security sanity check."""
    hash1 = hash_password("samePassword")
    hash2 = hash_password("samePassword")
    assert hash1 != hash2
    assert verify_password("samePassword", hash1)
    assert verify_password("samePassword", hash2)


def test_access_token_roundtrip_contains_expected_claims():
    user = models.User(id=1, username="testuser", password_hash="x", role="owner", is_active=True)
    token = create_access_token(user)
    payload = decode_access_token(token)

    assert payload is not None
    assert payload["sub"] == "1"
    assert payload["username"] == "testuser"
    assert payload["role"] == "owner"


def test_invalid_token_string_returns_none():
    assert decode_access_token("this-is-not-a-real-jwt") is None


def test_tampered_token_is_rejected():
    user = models.User(id=2, username="tampertest", password_hash="x", role="staff", is_active=True)
    token = create_access_token(user)
    tampered = token[:-3] + "xyz"
    assert decode_access_token(tampered) is None


def test_staff_and_owner_tokens_carry_different_roles():
    owner = models.User(id=1, username="o", password_hash="x", role="owner", is_active=True)
    staff = models.User(id=2, username="s", password_hash="x", role="staff", is_active=True)

    owner_payload = decode_access_token(create_access_token(owner))
    staff_payload = decode_access_token(create_access_token(staff))

    assert owner_payload["role"] == "owner"
    assert staff_payload["role"] == "staff"