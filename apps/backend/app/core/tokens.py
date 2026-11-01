"""
The one place Saha encodes and decodes JWTs.

Migrated from `python-jose` to `PyJWT` (security/AUDIT.md SAHA-026): python-jose
has been effectively unmaintained since 2021 and was the JWT implementation for
the entire auth system. Every call site now goes through this module, so the
library is swappable in one file rather than seven.

Hardening carried over and added:
  · algorithm is a fixed single-element allow-list — `none` can never be
    negotiated, and RS/HS confusion is impossible;
  · every token carries a `type` claim, checked on decode, so an email
    verification token can never be presented as an access token;
  · issuer and audience are asserted, so tokens minted by another system
    sharing the secret are rejected;
  · a `jti` is minted on every token, giving us a handle for future
    revocation and for correlating a token to audit events.
"""

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

import jwt

from app.core.config import settings

ISSUER = "saha"
AUDIENCE = "saha-api"


class TokenError(Exception):
    """Raised for any invalid, expired, or wrong-type token."""


def encode_token(
    subject: str,
    token_type: str,
    expires_in: timedelta,
    **extra_claims: Any,
) -> str:
    now = datetime.now(timezone.utc)
    payload: dict[str, Any] = {
        "sub": subject,
        "type": token_type,
        "iss": ISSUER,
        "aud": AUDIENCE,
        "iat": now,
        "nbf": now,
        "exp": now + expires_in,
        "jti": str(uuid.uuid4()),
        **extra_claims,
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def decode_token(token: str, expected_type: str | None = None) -> dict:
    """Decode and fully validate a token. Raises TokenError on any failure."""
    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],   # fixed allow-list, never from the token
            audience=AUDIENCE,
            issuer=ISSUER,
            options={"require": ["exp", "iat", "sub", "type"]},
        )
    except jwt.PyJWTError as exc:
        raise TokenError(str(exc)) from exc

    if expected_type is not None and payload.get("type") != expected_type:
        raise TokenError(f"expected a {expected_type} token")
    return payload
