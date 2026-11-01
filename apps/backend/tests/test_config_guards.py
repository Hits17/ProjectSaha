"""Configuration guards — the app must refuse to boot insecure.

Regression coverage for security/AUDIT.md SAHA-005: the deployed APP_ENV was
`staging`, which matched neither "production" nor "prod", so every check below
silently became a no-op on an internet-facing host. Hardening now keys off
`is_internet_facing`, and key-material checks run in *every* environment.
"""

import pytest
from pydantic import ValidationError

from app.core.config import Settings, validate_production_settings, validate_security_critical


def _prod_settings(**overrides) -> Settings:
    base = dict(
        APP_ENV="production",
        DEBUG=False,
        SECRET_KEY="a-real-64-char-random-secret-key-generated-for-production-use!!",
        VAULT_ENCRYPTION_KEY="a-real-32-byte-vault-key-for-prod",
        VAULT_ENCRYPTION_KEY_V2="a-real-32-byte-vault-key-v2-prod!",
        MINIO_ACCESS_KEY="a-real-access-key",
        MINIO_SECRET_KEY="a-real-secret-key",
        KYC_MOCK_MODE=False,
        ALLOWED_HOSTS=["api.saha.example"],
        CORS_ORIGINS=["https://app.saha.example"],
        COOKIE_SECURE=True,
        FRONTEND_URL="https://app.saha.example",
    )
    base.update(overrides)
    return Settings(_env_file=None, **base)


def test_clean_production_config_passes():
    assert validate_production_settings(_prod_settings()) == []


def test_development_env_skips_deployment_checks():
    dev = Settings(
        _env_file=None,
        APP_ENV="development",
        SECRET_KEY="a-real-64-char-random-secret-key-generated-for-development!!",
        VAULT_ENCRYPTION_KEY="a-real-32-byte-vault-key-for-dev!",
        MINIO_ACCESS_KEY="dev-access-key",
        MINIO_SECRET_KEY="dev-secret-key",
    )
    assert validate_production_settings(dev) == []


# ── SAHA-005: staging must be hardened exactly like production ───────────────

@pytest.mark.parametrize("env", ["staging", "production"])
def test_hardening_applies_to_every_internet_facing_env(env):
    problems = validate_production_settings(_prod_settings(APP_ENV=env, KYC_MOCK_MODE=True))
    assert any("KYC_MOCK_MODE" in p for p in problems), (
        f"{env} must be hardened — a mislabelled environment is how SAHA-004 stayed live"
    )


def test_unknown_app_env_is_rejected():
    """A typo must fail loudly rather than silently disabling every guard."""
    with pytest.raises(ValidationError):
        Settings(_env_file=None, APP_ENV="stagng")


# ── SAHA-001: key material is checked in every environment ──────────────────

def test_default_vault_key_rejected_even_in_development():
    dev = Settings(
        _env_file=None,
        APP_ENV="development",
        VAULT_ENCRYPTION_KEY="change-me-32-bytes-in-production!",
    )
    problems = validate_security_critical(dev)
    assert any("VAULT_ENCRYPTION_KEY" in p for p in problems)


def test_default_minio_credentials_rejected():
    problems = validate_security_critical(
        Settings(_env_file=None, APP_ENV="development",
                 MINIO_ACCESS_KEY="minioadmin", MINIO_SECRET_KEY="minioadmin")
    )
    assert any("MINIO_ACCESS_KEY" in p for p in problems)
    assert any("MINIO_SECRET_KEY" in p for p in problems)


def test_missing_v2_vault_key_rejected_when_deployed():
    problems = validate_production_settings(_prod_settings(VAULT_ENCRYPTION_KEY_V2=""))
    assert any("VAULT_ENCRYPTION_KEY_V2" in p for p in problems)


def test_localhost_frontend_url_rejected():
    problems = validate_production_settings(_prod_settings(FRONTEND_URL="http://localhost:3000"))
    assert any("FRONTEND_URL" in p for p in problems)


def test_external_llm_for_confidential_rejected():
    problems = validate_production_settings(
        _prod_settings(ALLOW_EXTERNAL_LLM_FOR_CONFIDENTIAL=True)
    )
    assert any("ALLOW_EXTERNAL_LLM" in p for p in problems)


def test_default_secret_key_rejected():
    problems = validate_production_settings(
        _prod_settings(SECRET_KEY="dev-secret-key-change-in-production")
    )
    assert any("SECRET_KEY" in p for p in problems)


def test_debug_rejected():
    problems = validate_production_settings(_prod_settings(DEBUG=True))
    assert any("DEBUG" in p for p in problems)


def test_kyc_mock_rejected():
    problems = validate_production_settings(_prod_settings(KYC_MOCK_MODE=True))
    assert any("KYC_MOCK_MODE" in p for p in problems)


def test_wildcard_hosts_rejected():
    problems = validate_production_settings(_prod_settings(ALLOWED_HOSTS=["*"]))
    assert any("ALLOWED_HOSTS" in p for p in problems)


def test_plaintext_cors_origins_rejected():
    """Not just localhost: any http:// origin with allow_credentials is a
    credential-leak path (security/AUDIT.md SAHA-010)."""
    for origin in ("http://localhost:3000", "http://10.0.0.228:8080"):
        problems = validate_production_settings(_prod_settings(CORS_ORIGINS=[origin]))
        assert any("CORS_ORIGINS" in p for p in problems), origin


def test_insecure_cookie_rejected():
    problems = validate_production_settings(_prod_settings(COOKIE_SECURE=False))
    assert any("COOKIE_SECURE" in p for p in problems)
