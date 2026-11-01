"""
AES-256-GCM encryption for IP vault files.
Encrypted bytes are stored in MinIO: nonce (12 bytes) || GCM ciphertext+tag.

Key versioning (security/AUDIT.md SAHA-001)
-------------------------------------------
The original design derived a single global key from VAULT_ENCRYPTION_KEY and
recorded `encryption_key_id = "v1"` on every asset — a field that was correct in
intent but never used, because there was only ever one key and no way to change
it. That key was found in production set to the placeholder string published in
.env.example, so every object was decryptable by anyone who had read the repo.

Objects now carry the version that encrypted them, and `_decrypt` selects the key
by version. New writes always use KEY_VERSION; V1 exists solely so pre-rotation
objects remain readable until they are re-encrypted (see scripts/reencrypt_vault.py).
Retiring V1 is then a matter of clearing VAULT_ENCRYPTION_KEY and deleting its
branch here.

Nothing in this module invents cryptography: AESGCM comes from `cryptography`'s
AEAD interface, the nonce is 12 bytes from os.urandom, and it is never reused.
"""

import hashlib
import os
import uuid

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from app.core.config import settings
from app.integrations import storage

# The version every new object is written with.
KEY_VERSION = "v2"


class VaultKeyError(RuntimeError):
    """Raised when the key for a requested version is not configured."""


def _key_material(version: str) -> str:
    material = {
        "v1": settings.VAULT_ENCRYPTION_KEY,
        "v2": settings.VAULT_ENCRYPTION_KEY_V2,
    }.get(version)
    if not material:
        raise VaultKeyError(
            f"Vault key '{version}' is not configured. Objects encrypted under it "
            f"cannot be read. Set the corresponding VAULT_ENCRYPTION_KEY* value."
        )
    return material


def _derive_key(version: str = KEY_VERSION) -> bytes:
    return hashlib.sha256(_key_material(version).encode()).digest()


def _encrypt(plaintext: bytes, version: str = KEY_VERSION) -> bytes:
    nonce = os.urandom(12)
    return nonce + AESGCM(_derive_key(version)).encrypt(nonce, plaintext, None)


def _decrypt(blob: bytes, version: str = KEY_VERSION) -> bytes:
    nonce, ciphertext = blob[:12], blob[12:]
    return AESGCM(_derive_key(version)).decrypt(nonce, ciphertext, None)


def content_digest(data: bytes) -> str:
    """SHA-256 over the plaintext. Recorded at ingest so a later read can prove
    the bytes are the bytes that were uploaded."""
    return hashlib.sha256(data).hexdigest()


async def store_encrypted_file(
    listing_id: uuid.UUID,
    filename: str,
    data: bytes,
    content_type: str = "application/octet-stream",
) -> dict:
    """Encrypt and upload a file. Returns storage metadata for the asset row.

    The storage key deliberately does NOT include the user-supplied filename:
    it is an opaque UUID path. A filename can contain path separators, unicode
    lookalikes and control characters, and object keys are not the place to
    discover that. The original name lives in the database column, where it is
    only ever emitted through a sanitised Content-Disposition header.
    """
    encrypted = _encrypt(data)
    asset_id = uuid.uuid4()
    key = f"vault/{listing_id}/{asset_id}.enc"
    await storage.upload_file(key, encrypted, "application/octet-stream")
    return {
        "storage_key": key,
        "encryption_key_id": KEY_VERSION,
        "file_size_bytes": len(data),
        "content_sha256": content_digest(data),
    }


# NOTE: no presigned-URL accessor on purpose. Vault objects are ciphertext —
# a raw storage URL would hand the caller undecryptable bytes. All reads go
# through decrypt_file() behind the authenticated download endpoint.
async def decrypt_file(storage_key: str, version: str = "v1") -> bytes:
    """Download and decrypt a vault file. Used for authorized access.

    `version` defaults to v1 for callers that predate key versioning; every
    current call site passes the asset's recorded encryption_key_id.
    """
    from app.integrations.storage import _s3_client

    async with _s3_client() as s3:
        resp = await s3.get_object(Bucket=settings.MINIO_BUCKET, Key=storage_key)
        async with resp["Body"] as stream:
            blob = await stream.read()

    return _decrypt(blob, version)


async def reencrypt_object(storage_key: str, from_version: str, to_version: str = KEY_VERSION) -> None:
    """Re-wrap one object under a newer key. Used by the rotation backfill."""
    plaintext = await decrypt_file(storage_key, from_version)
    await storage.upload_file(storage_key, _encrypt(plaintext, to_version), "application/octet-stream")
