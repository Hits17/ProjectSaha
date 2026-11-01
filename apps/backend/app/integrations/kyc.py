"""
KYC integration — Persona in production, mock mode in dev.
KYC_MOCK_MODE=true in .env auto-verifies without real Persona calls.
"""

import hashlib
import hmac
import uuid

import httpx

from app.core.config import settings


async def initiate_kyc_inquiry(user_email: str) -> dict:
    """
    Starts a KYC inquiry. Returns inquiry_id and session_token.
    Mock mode: returns fake values and can be immediately completed.
    """
    if settings.allows_mock_integrations and settings.KYC_MOCK_MODE:
        return {
            "inquiry_id": f"mock-inq-{uuid.uuid4()}",
            "session_token": f"mock-session-{uuid.uuid4()}",
            "mock": True,
        }

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            "https://withpersona.com/api/v1/inquiries",
            headers={
                "Authorization": f"Bearer {settings.PERSONA_API_KEY}",
                "Persona-Version": "2023-01-05",
                "Content-Type": "application/json",
            },
            json={
                "data": {
                    "attributes": {
                        "inquiry-template-id": settings.PERSONA_TEMPLATE_ID,
                        "reference-id": user_email,
                    }
                }
            },
        )
        response.raise_for_status()
        data = response.json()
        return {
            "inquiry_id": data["data"]["id"],
            "session_token": data["data"]["attributes"]["session-token"],
            "mock": False,
        }


def verify_persona_webhook_signature(payload: bytes, signature_header: str) -> bool:
    """Verifies Persona's t=timestamp,v1=signature header format.

    The mock bypass is gated on APP_ENV, not on KYC_MOCK_MODE. Previously this
    returned True unconditionally whenever the flag was set — and the flag was
    set on the internet-facing deployment, so the unauthenticated /webhooks/kyc
    endpoint accepted any request from anyone (security/AUDIT.md SAHA-004).
    """
    if settings.allows_mock_integrations and settings.KYC_MOCK_MODE:
        return True

    if not settings.PERSONA_WEBHOOK_SECRET:
        return False

    if not signature_header:
        return False

    try:
        parts = dict(p.split("=", 1) for p in signature_header.split(","))
        timestamp = parts.get("t", "")
        signature = parts.get("v1", "")
        signed_payload = f"{timestamp}.{payload.decode()}"
        expected = hmac.new(
            settings.PERSONA_WEBHOOK_SECRET.encode(),
            signed_payload.encode(),
            hashlib.sha256,
        ).hexdigest()
        return hmac.compare_digest(expected, signature)
    except Exception:
        return False


async def simulate_mock_completion(inquiry_id: str) -> dict:
    """In mock mode, simulates a successful Persona webhook payload."""
    return {
        "data": {
            "type": "inquiry",
            "id": inquiry_id,
            "attributes": {
                "status": "completed",
                "reference-id": "mock-user",
            },
        },
        "events": [{"name": "inquiry.approved"}],
    }
