"""
Regression suite for SAHA-001 — the vault key was the placeholder committed to
the repository.

`_derive_key()` computed SHA-256 over `VAULT_ENCRYPTION_KEY`, and that setting
was found on the live host set to one of the two placeholder strings that appear
in `config.py` and in `.env.example` — a file tracked in git. The same key
encrypts every negotiation message. Encryption at rest therefore provided zero
confidentiality against anyone who had read the repo, and there was no rotation
mechanism: `KEY_VERSION` was a constant that had never changed and
`encryption_key_id` was recorded on every asset but never read.

Rotation is only possible because objects now carry the version that encrypted
them. The V1 path must keep working until the backfill completes, then be
retired — `test_v1_objects_still_decrypt` is what makes that safe.
"""

import pytest

from app.core.config import Settings, validate_security_critical
from app.services import vault
from app.services.vault import (
    KEY_VERSION, VaultKeyError, _decrypt, _encrypt, content_digest,
)


def test_current_write_version_is_v2():
    assert KEY_VERSION == "v2", "new objects must be written under the rotated key"


def test_roundtrip_under_current_key():
    blob = _encrypt(b"unfiled patent claims")
    assert _decrypt(blob) == b"unfiled patent claims"


def test_v1_objects_still_decrypt():
    """Pre-rotation objects must remain readable until the backfill completes."""
    blob = _encrypt(b"legacy secret", version="v1")
    assert _decrypt(blob, version="v1") == b"legacy secret"


def test_v1_and_v2_produce_different_ciphertext():
    """If these matched, the rotation would be cosmetic."""
    assert _decrypt(_encrypt(b"x", "v1"), "v1") == _decrypt(_encrypt(b"x", "v2"), "v2")
    v1_key = vault._derive_key("v1")
    v2_key = vault._derive_key("v2")
    assert v1_key != v2_key


def test_wrong_version_fails_to_decrypt():
    blob = _encrypt(b"secret", version="v2")
    with pytest.raises(Exception):
        _decrypt(blob, version="v1")


def test_unconfigured_key_version_raises_clearly():
    with pytest.raises(VaultKeyError):
        _decrypt(b"0" * 32, version="v9")


def test_nonce_is_unique_per_encryption():
    blobs = {_encrypt(b"same plaintext")[:12] for _ in range(50)}
    assert len(blobs) == 50, "nonce reuse under AES-GCM is catastrophic"


def test_tampered_ciphertext_fails_authentication():
    blob = bytearray(_encrypt(b"deal terms"))
    blob[-1] ^= 0x01
    with pytest.raises(Exception):
        _decrypt(bytes(blob))


def test_content_digest_is_stable():
    assert content_digest(b"abc") == content_digest(b"abc")
    assert content_digest(b"abc") != content_digest(b"abd")


# ── The guard that would have caught this in the first place ────────────────

@pytest.mark.parametrize("placeholder", [
    "change-me-32-bytes-in-production!",
    "dev-vault-key-32-bytes-padding!!",
])
def test_placeholder_vault_key_rejected_in_every_environment(placeholder):
    """The original guard only ran when APP_ENV was exactly production or prod.
    The deployment was labelled `staging`, so it never ran at all (SAHA-005).
    Key material is now checked everywhere, unconditionally."""
    for env in ("development", "staging", "production"):
        problems = validate_security_critical(
            Settings(_env_file=None, APP_ENV=env, VAULT_ENCRYPTION_KEY=placeholder)
        )
        assert any("VAULT_ENCRYPTION_KEY" in p for p in problems), env


def test_messages_record_the_key_version_they_used():
    """Without this column, rotating the key would make every stored
    negotiation message permanently unreadable."""
    from app.db.models.proposal import Message

    assert "encryption_key_id" in Message.__table__.columns


def test_vault_assets_record_version_and_digest():
    from app.db.models.listing import IPVaultAsset

    for column in ("encryption_key_id", "content_sha256"):
        assert column in IPVaultAsset.__table__.columns
