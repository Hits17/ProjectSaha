"""Persona KYC webhook signature verification."""

import hashlib
import hmac

import pytest

from app.core.config import AppEnv, settings
from app.integrations.kyc import verify_persona_webhook_signature


def _header(payload: bytes, secret: str, timestamp: str = "1700000000") -> str:
    sig = hmac.new(secret.encode(), f"{timestamp}.{payload.decode()}".encode(), hashlib.sha256).hexdigest()
    return f"t={timestamp},v1={sig}"


def test_mock_mode_bypasses_verification_in_development_only(monkeypatch):
    """Development may skip the signature check; nothing else may.

    This test previously asserted the *opposite* — that KYC_MOCK_MODE alone was
    enough to accept any unsigned webhook. That flag was set on the public
    deployment, so the unauthenticated /webhooks/kyc endpoint accepted requests
    from anyone (security/AUDIT.md SAHA-004). The bypass is now gated on
    APP_ENV, and the assertion is inverted to match.
    """
    monkeypatch.setattr(settings, "APP_ENV", AppEnv.DEVELOPMENT)
    monkeypatch.setattr(settings, "KYC_MOCK_MODE", True)
    assert verify_persona_webhook_signature(b"{}", "")


@pytest.mark.parametrize("env", [AppEnv.STAGING, AppEnv.PRODUCTION])
def test_mock_mode_never_bypasses_outside_development(monkeypatch, env):
    monkeypatch.setattr(settings, "APP_ENV", env)
    monkeypatch.setattr(settings, "KYC_MOCK_MODE", True)
    monkeypatch.setattr(settings, "PERSONA_WEBHOOK_SECRET", "persona_secret")
    assert not verify_persona_webhook_signature(b"{}", "")


def test_unconfigured_secret_rejects_everything(monkeypatch):
    monkeypatch.setattr(settings, "APP_ENV", AppEnv.PRODUCTION)
    monkeypatch.setattr(settings, "KYC_MOCK_MODE", False)
    monkeypatch.setattr(settings, "PERSONA_WEBHOOK_SECRET", "")
    payload = b'{"data": {"id": "inq_1"}}'
    assert not verify_persona_webhook_signature(payload, _header(payload, ""))


def test_valid_signature_accepted(monkeypatch):
    monkeypatch.setattr(settings, "APP_ENV", AppEnv.PRODUCTION)
    monkeypatch.setattr(settings, "KYC_MOCK_MODE", False)
    monkeypatch.setattr(settings, "PERSONA_WEBHOOK_SECRET", "persona_secret")
    payload = b'{"data": {"id": "inq_1"}}'
    assert verify_persona_webhook_signature(payload, _header(payload, "persona_secret"))


def test_invalid_signature_rejected(monkeypatch):
    monkeypatch.setattr(settings, "APP_ENV", AppEnv.PRODUCTION)
    monkeypatch.setattr(settings, "KYC_MOCK_MODE", False)
    monkeypatch.setattr(settings, "PERSONA_WEBHOOK_SECRET", "persona_secret")
    payload = b'{"data": {"id": "inq_1"}}'
    assert not verify_persona_webhook_signature(payload, _header(payload, "wrong_secret"))


def test_missing_header_rejected(monkeypatch):
    monkeypatch.setattr(settings, "APP_ENV", AppEnv.PRODUCTION)
    monkeypatch.setattr(settings, "KYC_MOCK_MODE", False)
    monkeypatch.setattr(settings, "PERSONA_WEBHOOK_SECRET", "persona_secret")
    assert not verify_persona_webhook_signature(b"{}", "")
