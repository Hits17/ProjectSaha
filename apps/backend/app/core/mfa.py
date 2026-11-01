"""
TOTP (RFC 6238) multi-factor auth — dependency-free.

Secrets are generated as base32, provisioned to authenticator apps via an
otpauth:// URI, and stored ENCRYPTED at rest (AES-256-GCM, key derived from
SECRET_KEY) so a database leak doesn't expose the second factor.
"""

import base64
import hashlib
import hmac
import os
import struct
import time
from urllib.parse import quote

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from app.core.config import settings

_DIGITS = 6
_PERIOD = 30


def _mfa_key() -> bytes:
    # Distinct from the vault key: derive from SECRET_KEY with a domain tag.
    return hashlib.sha256(("mfa:" + settings.SECRET_KEY).encode()).digest()


def generate_secret() -> str:
    """Return a fresh base32 TOTP secret (no padding)."""
    return base64.b32encode(os.urandom(20)).decode().rstrip("=")


def encrypt_secret(secret: str) -> str:
    nonce = os.urandom(12)
    blob = nonce + AESGCM(_mfa_key()).encrypt(nonce, secret.encode(), None)
    return base64.b64encode(blob).decode()


def decrypt_secret(stored: str) -> str:
    blob = base64.b64decode(stored)
    nonce, ct = blob[:12], blob[12:]
    return AESGCM(_mfa_key()).decrypt(nonce, ct, None).decode()


def provisioning_uri(secret: str, account: str) -> str:
    """otpauth:// URI for QR provisioning in authenticator apps."""
    issuer = quote(settings.MFA_ISSUER)
    label = quote(f"{settings.MFA_ISSUER}:{account}")
    return (
        f"otpauth://totp/{label}?secret={secret}"
        f"&issuer={issuer}&algorithm=SHA1&digits={_DIGITS}&period={_PERIOD}"
    )


def _hotp(secret: str, counter: int) -> str:
    # base32 secrets may have had padding stripped; restore it for decode.
    padded = secret + "=" * ((8 - len(secret) % 8) % 8)
    key = base64.b32decode(padded, casefold=True)
    digest = hmac.new(key, struct.pack(">Q", counter), hashlib.sha1).digest()
    offset = digest[-1] & 0x0F
    code = (struct.unpack(">I", digest[offset : offset + 4])[0] & 0x7FFFFFFF) % (10 ** _DIGITS)
    return str(code).zfill(_DIGITS)


def verify(secret: str, code: str, *, window: int = 1) -> bool:
    """Verify a TOTP code, tolerating +/- `window` periods of clock skew.
    Constant-time comparison per candidate to avoid timing leaks.

    Prefer `verify_with_counter` where the accepted counter can be persisted —
    this variant cannot detect replay."""
    return verify_with_counter(secret, code, window=window)[0]


def verify_with_counter(
    secret: str, code: str, *, window: int = 1, last_counter: int | None = None
) -> tuple[bool, int | None]:
    """Verify a TOTP code and return the counter it matched.

    Returns (ok, matched_counter). When `last_counter` is supplied, any code
    from that counter or earlier is rejected: TOTP codes are valid for a whole
    period (plus skew window), so without this an intercepted code is reusable
    for up to 90 seconds (security/AUDIT.md SAHA-030). Callers persist the
    returned counter on the user record.
    """
    if not code or not code.strip().isdigit():
        return False, None
    code = code.strip()
    now = int(time.time() // _PERIOD)
    for drift in range(-window, window + 1):
        candidate = now + drift
        if last_counter is not None and candidate <= last_counter:
            continue  # already used — replay
        if hmac.compare_digest(_hotp(secret, candidate), code):
            return True, candidate
    return False, None
