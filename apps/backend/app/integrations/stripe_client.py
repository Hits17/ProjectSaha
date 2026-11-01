"""
Stripe integration for escrow payments.
Mock mode: if STRIPE_SECRET_KEY is empty or contains 'REPLACE_ME', all operations are simulated.
"""

import hashlib
import hmac
import time

import structlog
from app.core.config import settings

logger = structlog.get_logger()


def is_mock_mode() -> bool:
    """True only in development with no real key configured.

    Mock mode marks escrow funded without money moving, and escrow funding is
    what releases the seller's vault to the buyer. Gating it on an empty key
    alone meant an internet-facing deployment silently ran a payment step that
    moved nothing (security/AUDIT.md SAHA-036). Outside development an
    unconfigured key is a boot-time error, not a fallback.
    """
    key = settings.STRIPE_SECRET_KEY
    unconfigured = not key or "REPLACE_ME" in key
    if not settings.allows_mock_integrations:
        if unconfigured:
            raise RuntimeError(
                "STRIPE_SECRET_KEY is not configured. Payments cannot run in mock "
                "mode outside development."
            )
        return False
    return unconfigured


def _to_cents(amount_usd: float) -> int:
    return int(round(amount_usd * 100))


async def create_payment_intent(amount_usd: float, metadata: dict) -> dict:
    """Create a Stripe PaymentIntent for escrow. Returns {id, client_secret, status}."""
    amount_cents = _to_cents(amount_usd)

    if is_mock_mode():
        intent_id = f"pi_mock_{abs(hash(str(metadata)))}"
        logger.info("stripe_mock_payment_intent", amount_cents=amount_cents, intent_id=intent_id)
        return {"id": intent_id, "client_secret": f"{intent_id}_secret", "status": "requires_payment_method"}

    import httpx
    async with httpx.AsyncClient(timeout=30.0) as client:
        data = {
            "amount": amount_cents,
            "currency": "usd",
            "payment_method_types[]": "card",
        }
        for k, v in metadata.items():
            data[f"metadata[{k}]"] = str(v)
        resp = await client.post(
            "https://api.stripe.com/v1/payment_intents",
            headers={"Authorization": f"Bearer {settings.STRIPE_SECRET_KEY}"},
            data=data,
        )
        resp.raise_for_status()
        pi = resp.json()
    return {"id": pi["id"], "client_secret": pi["client_secret"], "status": pi["status"]}


async def confirm_payment_intent(intent_id: str) -> dict:
    """Confirm a PaymentIntent (used in mock mode to simulate payment success)."""
    if is_mock_mode():
        logger.info("stripe_mock_confirm", intent_id=intent_id)
        return {"id": intent_id, "status": "succeeded"}

    import httpx
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(
            f"https://api.stripe.com/v1/payment_intents/{intent_id}/confirm",
            headers={"Authorization": f"Bearer {settings.STRIPE_SECRET_KEY}"},
            data={"payment_method": "pm_card_visa"},
        )
        resp.raise_for_status()
    return resp.json()


async def create_transfer(amount_usd: float, destination: str, metadata: dict) -> dict:
    """Transfer funds to a connected account. Mock returns fake transfer ID."""
    if is_mock_mode():
        transfer_id = f"tr_mock_{abs(hash(destination + str(amount_usd)))}"
        logger.info("stripe_mock_transfer", amount_usd=amount_usd, destination=destination)
        return {"id": transfer_id, "status": "paid"}

    import httpx
    amount_cents = _to_cents(amount_usd)
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(
            "https://api.stripe.com/v1/transfers",
            headers={"Authorization": f"Bearer {settings.STRIPE_SECRET_KEY}"},
            data={"amount": amount_cents, "currency": "usd", "destination": destination},
        )
        resp.raise_for_status()
    return resp.json()


def verify_webhook_signature(payload: bytes, signature_header: str, tolerance_seconds: int = 300) -> bool:
    """
    Verifies Stripe's `Stripe-Signature: t=<ts>,v1=<hmac>` header.
    Rejects stale timestamps (replay protection) and bad signatures.
    """
    secret = settings.STRIPE_WEBHOOK_SECRET
    if not secret or "REPLACE_ME" in secret:
        return False

    try:
        parts = {}
        for item in signature_header.split(","):
            k, _, v = item.strip().partition("=")
            parts.setdefault(k, []).append(v)
        timestamp = int(parts["t"][0])
        signatures = parts.get("v1", [])
    except (KeyError, ValueError, IndexError):
        return False

    if abs(time.time() - timestamp) > tolerance_seconds:
        return False

    signed_payload = f"{timestamp}.{payload.decode()}"
    expected = hmac.new(secret.encode(), signed_payload.encode(), hashlib.sha256).hexdigest()
    return any(hmac.compare_digest(expected, sig) for sig in signatures)
