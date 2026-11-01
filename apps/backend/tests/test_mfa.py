"""TOTP MFA: secret generation, encryption round-trip, and code verification
with clock-skew tolerance. Dependency-free (RFC 6238)."""

import time

from app.core import mfa


def test_secret_is_base32_and_unique():
    a = mfa.generate_secret()
    b = mfa.generate_secret()
    assert a != b
    # base32 alphabet only
    assert all(c in "ABCDEFGHIJKLMNOPQRSTUVWXYZ234567" for c in a)


def test_encrypt_decrypt_round_trip():
    secret = mfa.generate_secret()
    enc = mfa.encrypt_secret(secret)
    assert enc != secret  # actually encrypted
    assert mfa.decrypt_secret(enc) == secret


def test_current_code_verifies():
    secret = mfa.generate_secret()
    counter = int(time.time() // 30)
    code = mfa._hotp(secret, counter)
    assert mfa.verify(secret, code)


def test_wrong_code_rejected():
    secret = mfa.generate_secret()
    assert not mfa.verify(secret, "000000")
    assert not mfa.verify(secret, "not-a-code")
    assert not mfa.verify(secret, "")


def test_skew_window_accepts_previous_period():
    secret = mfa.generate_secret()
    prev = mfa._hotp(secret, int(time.time() // 30) - 1)
    assert mfa.verify(secret, prev, window=1)


def test_provisioning_uri_shape():
    uri = mfa.provisioning_uri("ABC234", "user@example.com")
    assert uri.startswith("otpauth://totp/")
    assert "secret=ABC234" in uri
    assert "issuer=" in uri
