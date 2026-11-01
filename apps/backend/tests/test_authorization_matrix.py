"""
Authorization regression suite.

Two classes of defect are covered, both of which a unit-test-only suite missed:

**SAHA-007** — `/disburse` was wired to `_check_access` (either party) where it
needed `_check_buyer`. The seller could therefore transfer the escrow to
themselves the moment the buyer funded it, with no approval, inspection period
or dispute window. One wrong helper, in one handler, and nothing caught it.

**SAHA-022** — authorization was enforced by six hand-rolled predicate shapes
across eight modules, with no shared primitive and no default-deny. SAHA-007 is
what that produces. `test_every_route_declares_an_auth_dependency` is the
structural guard: a new route added without a guard fails here rather than
shipping open.
"""

import uuid

import pytest
from fastapi import HTTPException

from app.db.models.transaction import TransactionStatus
from app.services import settlement as settlement_svc


class _Txn:
    """Minimal stand-in — these predicates are pure functions over ids."""

    def __init__(self, buyer, seller, status=TransactionStatus.ESCROW_FUNDED):
        self.buyer_id = buyer
        self.seller_id = seller
        self.status = status
        self.escrow_funded_at = "2026-01-01T00:00:00Z"
        self.stripe_payment_intent_id = "pi_test"


BUYER = uuid.uuid4()
SELLER = uuid.uuid4()
STRANGER = uuid.uuid4()


# ── SAHA-007: escrow release ────────────────────────────────────────────────

def test_seller_cannot_release_escrow_to_themselves():
    with pytest.raises(HTTPException) as exc:
        settlement_svc._assert_may_release(_Txn(BUYER, SELLER), SELLER, actor_is_admin=False)
    assert exc.value.status_code == 403
    assert "buyer" in exc.value.detail.lower()


def test_buyer_can_release_escrow():
    settlement_svc._assert_may_release(_Txn(BUYER, SELLER), BUYER, actor_is_admin=False)


def test_stranger_cannot_release_escrow():
    with pytest.raises(HTTPException):
        settlement_svc._assert_may_release(_Txn(BUYER, SELLER), STRANGER, actor_is_admin=False)


def test_admin_can_release_escrow_for_dispute_resolution():
    settlement_svc._assert_may_release(_Txn(BUYER, SELLER), STRANGER, actor_is_admin=True)


# ── Vault access ────────────────────────────────────────────────────────────

def test_seller_always_reaches_their_own_vault():
    settlement_svc._assert_vault_access(
        _Txn(BUYER, SELLER, TransactionStatus.PENDING_LEGAL), SELLER
    )


def test_buyer_blocked_before_escrow_is_funded():
    with pytest.raises(HTTPException) as exc:
        settlement_svc._assert_vault_access(
            _Txn(BUYER, SELLER, TransactionStatus.CONTRACT_REVIEW), BUYER
        )
    assert exc.value.status_code == 403


def test_buyer_reaches_vault_once_escrow_is_funded():
    settlement_svc._assert_vault_access(_Txn(BUYER, SELLER), BUYER)


def test_stranger_never_reaches_the_vault():
    for status in TransactionStatus:
        with pytest.raises(HTTPException):
            settlement_svc._assert_vault_access(_Txn(BUYER, SELLER, status), STRANGER)


def test_funded_status_without_payment_evidence_is_refused(monkeypatch):
    """Defence in depth for SAHA-036: the status alone is not proof money moved."""
    from app.core.config import AppEnv, settings

    monkeypatch.setattr(settings, "APP_ENV", AppEnv.PRODUCTION)
    txn = _Txn(BUYER, SELLER)
    txn.escrow_funded_at = None
    with pytest.raises(HTTPException) as exc:
        settlement_svc._assert_vault_access(txn, BUYER)
    assert exc.value.status_code == 403


# ── SAHA-022: structural default-deny ───────────────────────────────────────

# Routes that are public by design. Everything else must name a guard.
PUBLIC_ROUTES = {
    ("/api/v1/social/media/{media_id}", "GET"),  # post visibility checked before object access
    ("/api/v1/institutions", "GET"),
    ("/api/v1/institutions/policy", "GET"),
    ("/api/v1/institutions/{institution_id}", "GET"),
    ("/api/v1/open-discovery", "GET"),
    ("/api/v1/projects", "GET"),
    ("/api/v1/projects/{project_id}", "GET"),
    ("/api/v1/projects/{project_id}/tasks", "GET"),
    ("/health/live", "GET"),
    ("/health/ready", "GET"),
    ("/api/v1/auth/register", "POST"),
    ("/api/v1/auth/login", "POST"),
    ("/api/v1/auth/refresh", "POST"),          # authenticated by the refresh token itself
    ("/api/v1/auth/verify-email/confirm", "POST"),  # authenticated by the signed token
    ("/api/v1/webhooks/kyc", "POST"),          # authenticated by HMAC signature
    ("/api/v1/webhooks/stripe", "POST"),       # authenticated by HMAC signature
    ("/api/v1/listings/public", "GET"),        # teaser tier — see test_disclosure_tiers
    ("/api/v1/listings/{listing_id}", "GET"),  # teaser tier for non-owners
    ("/api/v1/search", "POST"),                # optional auth; teaser tier only
    ("/api/v1/notifications/stream", "GET"),   # authenticated by a scoped SSE ticket
    ("/openapi.json", "GET"),
    ("/docs", "GET"),
    ("/docs/oauth2-redirect", "GET"),
    ("/redoc", "GET"),
}

_AUTH_DEPENDENCIES = {
    "get_current_user", "get_optional_user", "require_verified_user",
    "require_admin", "require_email_verified", "require_step_up", "require_collaborator", "require_chat_link_auth",
}


def _declares_auth(route) -> bool:
    for dep in getattr(route.dependant, "dependencies", []):
        if getattr(dep.call, "__name__", "") in _AUTH_DEPENDENCIES:
            return True
    return False


def test_every_route_declares_an_auth_dependency():
    """Deny-by-default, enforced structurally.

    Authorization is scattered across handlers, so the guard against the next
    SAHA-007 is a test that refuses to let an unguarded route exist at all.
    Adding a genuinely public route means adding it to PUBLIC_ROUTES above —
    a deliberate, reviewable act.
    """
    from app.main import app

    unguarded = []
    for route in app.routes:
        path = getattr(route, "path", None)
        methods = getattr(route, "methods", set()) or set()
        if path is None or not hasattr(route, "dependant"):
            continue
        for method in methods - {"HEAD", "OPTIONS"}:
            if (path, method) in PUBLIC_ROUTES:
                continue
            if not _declares_auth(route):
                unguarded.append(f"{method} {path}")

    assert not unguarded, (
        "These routes declare no authentication dependency:\n  "
        + "\n  ".join(sorted(unguarded))
        + "\nEither add a guard, or add the route to PUBLIC_ROUTES with a reason."
    )


def test_high_value_actions_require_step_up():
    """Escrow release, contract execution and vault egress are irreversible or
    disclose trade secrets — a stolen access token alone must not suffice."""
    from app.main import app

    expected = {
        ("/api/v1/transactions/{transaction_id}/disburse", "POST"),
        ("/api/v1/transactions/{transaction_id}/sign", "POST"),
        ("/api/v1/transactions/{transaction_id}/vault-access/{asset_id}/download", "GET"),
    }
    found = set()
    for route in app.routes:
        path = getattr(route, "path", None)
        if path is None or not hasattr(route, "dependant"):
            continue
        for dep in route.dependant.dependencies:
            if getattr(dep.call, "__name__", "") == "require_step_up":
                for method in getattr(route, "methods", set()) - {"HEAD", "OPTIONS"}:
                    found.add((path, method))

    assert expected <= found, f"missing step-up on: {expected - found}"
