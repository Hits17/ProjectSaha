"""AES-256-GCM vault encryption invariants."""

import pytest

from app.services.vault import _decrypt, _encrypt


def test_encrypt_decrypt_roundtrip():
    plaintext = b"proprietary formula: 42% unobtainium"
    blob = _encrypt(plaintext)
    assert blob != plaintext
    assert _decrypt(blob) == plaintext


def test_unique_nonce_per_encryption():
    blob_a = _encrypt(b"same input")
    blob_b = _encrypt(b"same input")
    assert blob_a != blob_b  # random nonce → different ciphertext every time


def test_tampered_ciphertext_fails_authentication():
    blob = bytearray(_encrypt(b"integrity matters"))
    blob[-1] ^= 0xFF  # flip a bit in the GCM tag
    with pytest.raises(Exception):
        _decrypt(bytes(blob))
