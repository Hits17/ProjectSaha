"""
Shared slowapi rate limiter. Lives in its own module so routers can import it
without a circular import through main.py.

Keying: per-user when a valid Bearer token is present, else per-client-IP
(honouring X-Forwarded-For set by the reverse proxy).

Two layers of protection:
  1. `default_limits` (below) are enforced on EVERY route by SlowAPIMiddleware,
     registered in main.py. This is the anti-abuse backstop — no endpoint is
     left unthrottled.
  2. Stricter per-route ceilings via the `@limiter.limit(...)` decorator using
     the tiered constants below (auth, expensive/AI, money-movement, writes).
     A decorated route needs a `request: Request` parameter in its signature.
"""

from fastapi import Request
from slowapi import Limiter

from app.core.clientip import rate_limit_ip
from app.core.config import settings
from app.core.tokens import decode_token

# --- Tiered ceilings (per rate-limit key, i.e. per user or per client IP) -----
# Applied on top of DEFAULT_LIMITS via the @limiter.limit decorator.
AUTH_LIMIT = "10/minute"          # login / register — brute-force surface
REFRESH_LIMIT = "60/minute"       # token refresh — legitimately frequent
MONEY_LIMIT = "10/minute"         # escrow + disbursement — irreversible money movement
EXPENSIVE_LIMIT = "20/minute"     # AI dialogue, contract drafting, file uploads, search
WRITE_LIMIT = "60/minute"         # ordinary create/update/delete + messaging
ANON_READ_LIMIT = "60/minute"     # unauthenticated browse — corpus-harvesting surface
KYC_LIMIT = "5/hour"              # identity verification — no legitimate high volume
VAULT_DOWNLOAD_LIMIT = "30/hour"  # confidential document egress — bulk pull is an incident
VOTE_LIMIT = "120/hour"           # social voting — generous for real use, blunts brigading

# Backstop applied to every route by SlowAPIMiddleware. Generous enough not to
# affect legitimate use (incl. health polling) but low enough to blunt scripted
# abuse. Depends on the reverse proxy setting X-Forwarded-For (see _rate_limit_key).
DEFAULT_LIMITS = ["1000/minute", "20000/hour"]


def _rate_limit_key(request: Request) -> str:
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        try:
            payload = decode_token(auth[7:])
            if payload.get("sub"):
                return f"user:{payload['sub']}"
        except Exception:
            pass
    # Client-supplied forwarding headers are NOT trusted here — see
    # app.core.clientip for why (security/AUDIT.md SAHA-011).
    return rate_limit_ip(request)


limiter = Limiter(
    key_func=_rate_limit_key,
    default_limits=DEFAULT_LIMITS,
    storage_uri=settings.REDIS_URL,
    in_memory_fallback_enabled=True,  # keep serving (per-process limits) if Redis is down
)
