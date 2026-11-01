"""
Regression suite for SAHA-011 — X-Forwarded-For was client-authored.

nginx is configured with `$proxy_add_x_forwarded_for`, which *appends* the peer
to whatever the client sent. The old code read `X-Forwarded-For.split(",")[0]` —
the FIRST element — in both the rate limiter and the audit logger. So a caller
could set the header to any value and have it believed: IP rate limits were
bypassable by rotating a header, and `audit_logs.ip_address` was forgeable.

`audit_logs.ip_address` is Postgres INET, so a non-IP value could also abort the
audit write entirely — an attacker suppressing their own trail. Everything
returned here is guaranteed to parse as an IP address.
"""

import pytest

from app.core.clientip import client_ip, rate_limit_ip


class _Req:
    def __init__(self, peer, **headers):
        self.client = type("C", (), {"host": peer})() if peer else None
        self.headers = {k.replace("_", "-"): v for k, v in headers.items()}


@pytest.fixture(autouse=True)
def _clear_cache():
    from app.core.clientip import _trusted_networks
    _trusted_networks.cache_clear()
    yield
    _trusted_networks.cache_clear()


# ── Direct connections trust nothing ────────────────────────────────────────

def test_untrusted_peer_headers_are_ignored():
    """A client connecting directly can claim anything; none of it is believed."""
    req = _Req("203.0.113.9", **{"X-Forwarded-For": "1.2.3.4", "CF-Connecting-IP": "5.6.7.8"})
    assert client_ip(req) == "203.0.113.9"


# ── Behind the trusted proxy chain ──────────────────────────────────────────

def test_edge_header_is_used_from_a_trusted_peer():
    req = _Req("127.0.0.1", **{"CF-Connecting-IP": "198.51.100.7"})
    assert client_ip(req) == "198.51.100.7"


def test_spoofed_forwarded_for_does_not_win_over_the_edge_header():
    req = _Req("127.0.0.1", **{
        "X-Forwarded-For": "1.2.3.4, 198.51.100.7, 127.0.0.1",
        "CF-Connecting-IP": "198.51.100.7",
    })
    assert client_ip(req) == "198.51.100.7"


def test_forwarded_for_is_walked_from_the_right():
    """Without the edge header, the rightmost untrusted hop is the real client —
    everything to its left is caller-supplied."""
    req = _Req("127.0.0.1", **{"X-Forwarded-For": "1.2.3.4, 198.51.100.7"})
    assert client_ip(req) == "198.51.100.7"


def test_attacker_cannot_forge_by_prepending():
    """The old bug, stated directly: element [0] must not be trusted."""
    req = _Req("127.0.0.1", **{"X-Forwarded-For": "6.6.6.6, 198.51.100.7"})
    assert client_ip(req) != "6.6.6.6"


def test_all_trusted_hops_falls_back_to_the_peer():
    req = _Req("127.0.0.1", **{"X-Forwarded-For": "127.0.0.1, ::1"})
    assert client_ip(req) == "127.0.0.1"


# ── Everything returned must be a valid INET value ──────────────────────────

@pytest.mark.parametrize("bad", [
    "not-an-ip", "'; DROP TABLE audit_logs; --", "999.999.999.999", "", "   ",
    "<script>alert(1)</script>",
])
def test_malformed_header_values_are_discarded(bad):
    """A non-IP value in an INET column aborts the insert — which is an audit
    suppression vector, not just a data-quality problem."""
    req = _Req("127.0.0.1", **{"CF-Connecting-IP": bad})
    result = client_ip(req)
    assert result is None or _parses_as_ip(result)


def test_ipv6_peer_is_handled():
    req = _Req("::1", **{"CF-Connecting-IP": "2001:db8::1"})
    assert client_ip(req) == "2001:db8::1"


def test_bracketed_ipv6_with_port_is_parsed():
    req = _Req("127.0.0.1", **{"CF-Connecting-IP": "[2001:db8::1]:443"})
    assert client_ip(req) == "2001:db8::1"


def test_ipv4_with_port_is_parsed():
    req = _Req("127.0.0.1", **{"CF-Connecting-IP": "198.51.100.7:51234"})
    assert client_ip(req) == "198.51.100.7"


def test_missing_client_is_tolerated():
    assert client_ip(_Req(None)) is None
    assert rate_limit_ip(_Req(None)) == "unknown"


def _parses_as_ip(value: str) -> bool:
    import ipaddress
    try:
        ipaddress.ip_address(value)
        return True
    except ValueError:
        return False


# ── Rate-limit keying ───────────────────────────────────────────────────────

def test_rate_limit_key_cannot_be_rotated_by_header():
    from app.core.ratelimit import _rate_limit_key

    keys = {
        _rate_limit_key(_Req("203.0.113.9", **{"X-Forwarded-For": f"10.0.0.{i}"}))
        for i in range(20)
    }
    assert keys == {"203.0.113.9"}, (
        "header rotation must not produce distinct rate-limit buckets"
    )


def test_authenticated_requests_key_on_the_user():
    from app.core.ratelimit import _rate_limit_key
    from app.core.security import create_access_token
    import uuid

    uid = uuid.uuid4()
    token = create_access_token(str(uid), "creator")
    req = _Req("203.0.113.9", **{"Authorization": f"Bearer {token}"})
    assert _rate_limit_key(req) == f"user:{uid}"
