"""
Trusted resolution of the real client IP address.

Why this module exists (security/AUDIT.md SAHA-011): the previous code read
`X-Forwarded-For.split(",")[0]` — the FIRST element — in both the rate limiter
and the audit logger. nginx is configured with `$proxy_add_x_forwarded_for`,
which *appends* the peer to whatever the client sent, so element [0] is entirely
client-authored. That made IP rate limits bypassable by rotating a header, and
made `audit_logs.ip_address` attacker-forgeable.

The real request chain is:

    client → Cloudflare edge → cloudflared (localhost) → nginx → uvicorn

so the socket peer is always loopback and `X-Real-IP` (set by nginx from
`$remote_addr`) is always 127.0.0.1. The only trustworthy source of the true
client address is the header the Cloudflare edge sets, and it is trustworthy
*only* when the request genuinely arrived through that chain — which we
establish by requiring the socket peer to be a configured trusted proxy.

Rules:
  1. Direct connection (peer is not a trusted proxy): trust nothing, use the socket.
  2. Via a trusted proxy: prefer the edge header; else walk X-Forwarded-For from
     the RIGHT, skipping trusted hops, and take the first untrusted value.
  3. Anything that does not parse as an IP address is discarded. `audit_logs.
     ip_address` is Postgres INET — a non-IP value would abort the audit write,
     which is exactly the audit-suppression vector we are closing.
"""

import ipaddress
from functools import lru_cache

from fastapi import Request

from app.core.config import settings


@lru_cache(maxsize=1)
def _trusted_networks() -> tuple[ipaddress.IPv4Network | ipaddress.IPv6Network, ...]:
    nets = []
    for entry in settings.TRUSTED_PROXY_CIDRS:
        try:
            nets.append(ipaddress.ip_network(entry.strip(), strict=False))
        except ValueError:
            continue
    return tuple(nets)


def _parse(value: str | None) -> ipaddress.IPv4Address | ipaddress.IPv6Address | None:
    if not value:
        return None
    candidate = value.strip()
    # Tolerate "ip:port" and bracketed IPv6 forms some proxies emit.
    if candidate.startswith("[") and "]" in candidate:
        candidate = candidate[1 : candidate.index("]")]
    try:
        return ipaddress.ip_address(candidate)
    except ValueError:
        if candidate.count(":") == 1:  # IPv4:port
            try:
                return ipaddress.ip_address(candidate.rsplit(":", 1)[0])
            except ValueError:
                return None
        return None


def _is_trusted(addr) -> bool:
    return any(addr in net for net in _trusted_networks())


def client_ip(request: Request) -> str | None:
    """Best-effort real client IP, or None when it cannot be established.

    Returns a string that is guaranteed to parse as an IP address, so it is
    always safe to store in an INET column.
    """
    peer = _parse(request.client.host if request.client else None)

    # Rule 1 — a direct connection can forge any header, so ignore all of them.
    if peer is None or not _is_trusted(peer):
        return str(peer) if peer else None

    # Rule 2a — the edge header, set by infrastructure the client cannot reach.
    edge = _parse(request.headers.get(settings.TRUSTED_CLIENT_IP_HEADER))
    if edge is not None:
        return str(edge)

    # Rule 2b — walk X-Forwarded-For right-to-left past our own trusted hops.
    forwarded = request.headers.get("X-Forwarded-For", "")
    for raw in reversed(forwarded.split(",")):
        addr = _parse(raw)
        if addr is None:
            continue
        if not _is_trusted(addr):
            return str(addr)

    return str(peer)


def rate_limit_ip(request: Request) -> str:
    """Same resolution, with a stable fallback — a rate-limit key is never None."""
    return client_ip(request) or "unknown"
