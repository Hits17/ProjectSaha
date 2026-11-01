"""Stripe client: mock-mode detection, cent conversion, webhook signature verification."""

import hashlib
import hmac
import json
import time

import pytest

from app.core.config import AppEnv, settings
from app.integrations import stripe_client


def test_mock_mode_requires_development(monkeypatch):
    """Outside development an unconfigured Stripe key is a hard error.

    Mock mode marks escrow funded with no money moving, and escrow funding is
    what releases the seller's vault to the buyer (security/AUDIT.md SAHA-036).
    Falling back to it on a deployed environment is never correct.
    """
    monkeypatch.setattr(settings, "APP_ENV", AppEnv.PRODUCTION)
    monkeypatch.setattr(settings, "STRIPE_SECRET_KEY", "")
    with pytest.raises(RuntimeError):
        stripe_client.is_mock_mode()


def test_mock_mode_for_placeholder_key(monkeypatch):
    monkeypatch.setattr(settings, "APP_ENV", AppEnv.DEVELOPMENT)
    monkeypatch.setattr(settings, "STRIPE_SECRET_KEY", "sk_test_REPLACE_ME")
    assert stripe_client.is_mock_mode()


def test_mock_mode_for_empty_key(monkeypatch):
    monkeypatch.setattr(settings, "APP_ENV", AppEnv.DEVELOPMENT)
    # Empty key must NOT fall through to live API calls
    monkeypatch.setattr(settings, "STRIPE_SECRET_KEY", "")
    assert stripe_client.is_mock_mode()


def test_live_mode_for_real_key(monkeypatch):
    monkeypatch.setattr(settings, "STRIPE_SECRET_KEY", "sk_live_abc123")
    assert not stripe_client.is_mock_mode()


def test_to_cents_avoids_float_truncation():
    # 19.99 * 100 == 1998.9999... — int() would lose a cent
    assert stripe_client._to_cents(19.99) == 1999
    assert stripe_client._to_cents(0.07) == 7
    assert stripe_client._to_cents(40000) == 4000000


def _signed_header(payload: bytes, secret: str, timestamp: int | None = None) -> str:
    ts = timestamp or int(time.time())
    sig = hmac.new(secret.encode(), f"{ts}.{payload.decode()}".encode(), hashlib.sha256).hexdigest()
    return f"t={ts},v1={sig}"


def test_webhook_signature_valid(monkeypatch):
    monkeypatch.setattr(settings, "STRIPE_WEBHOOK_SECRET", "whsec_unit_test")
    payload = json.dumps({"type": "payment_intent.succeeded"}).encode()
    header = _signed_header(payload, "whsec_unit_test")
    assert stripe_client.verify_webhook_signature(payload, header)


def test_webhook_signature_wrong_secret(monkeypatch):
    monkeypatch.setattr(settings, "STRIPE_WEBHOOK_SECRET", "whsec_unit_test")
    payload = b"{}"
    header = _signed_header(payload, "whsec_attacker")
    assert not stripe_client.verify_webhook_signature(payload, header)


def test_webhook_signature_stale_timestamp(monkeypatch):
    monkeypatch.setattr(settings, "STRIPE_WEBHOOK_SECRET", "whsec_unit_test")
    payload = b"{}"
    header = _signed_header(payload, "whsec_unit_test", timestamp=int(time.time()) - 3600)
    assert not stripe_client.verify_webhook_signature(payload, header)


def test_webhook_rejected_when_secret_unconfigured(monkeypatch):
    monkeypatch.setattr(settings, "STRIPE_WEBHOOK_SECRET", "whsec_REPLACE_ME")
    payload = b"{}"
    header = _signed_header(payload, "whsec_REPLACE_ME")
    assert not stripe_client.verify_webhook_signature(payload, header)


def test_webhook_malformed_header(monkeypatch):
    monkeypatch.setattr(settings, "STRIPE_WEBHOOK_SECRET", "whsec_unit_test")
    assert not stripe_client.verify_webhook_signature(b"{}", "garbage")
    assert not stripe_client.verify_webhook_signature(b"{}", "")
