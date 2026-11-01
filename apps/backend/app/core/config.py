import enum
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class AppEnv(str, enum.Enum):
    """Closed set, so a typo can never silently downgrade security.

    Before this was a free-form string, the deployed value was `staging` — which
    matched neither "production" nor "prod", so every production guard silently
    became a no-op on an internet-facing host (security/AUDIT.md SAHA-005).
    """

    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Application
    APP_NAME: str = "Saha"
    APP_ENV: AppEnv = AppEnv.DEVELOPMENT
    DEBUG: bool = True
    SECRET_KEY: str = "change-me-in-production"

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://saha:saha@localhost:5432/saha"

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"

    # MinIO / S3
    MINIO_ENDPOINT: str = "localhost:9000"
    MINIO_ACCESS_KEY: str = "minioadmin"
    MINIO_SECRET_KEY: str = "minioadmin"
    MINIO_BUCKET: str = "saha-vault"
    MINIO_SECURE: bool = False

    # Qdrant
    QDRANT_URL: str = "http://localhost:6333"
    QDRANT_COLLECTION: str = "ip_listings"
    QDRANT_API_KEY: str = ""

    # Email (MailHog in dev)
    SMTP_HOST: str = "localhost"
    SMTP_PORT: int = 1025
    SMTP_USERNAME: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_USE_TLS: bool = False   # forced on outside development — see validate_*
    EMAIL_FROM: str = "noreply@saha.local"

    # Multi-provider AI
    LLM_PROVIDER: str = "nvidia"  # anthropic | nvidia | ollama | auto
    ANTHROPIC_API_KEY: str = ""
    NVIDIA_API_KEY: str = ""
    # Chat model on the NVIDIA endpoint. Override via env when the account's
    # model access changes. diffusiongemma is a "thinking" model — see
    # nvidia.py for the chat_template_kwargs it needs.
    NVIDIA_CHAT_MODEL: str = "google/diffusiongemma-26b-a4b-it"
    OLLAMA_BASE_URL: str = "http://localhost:11434"

    # Data-tier policy for AI calls. Confidential and trade-secret content must
    # not leave the trust boundary for third-party inference (SAHA-013). Flip
    # this only with a signed DPA and a documented transfer basis.
    ALLOW_EXTERNAL_LLM_FOR_CONFIDENTIAL: bool = False

    # JWT
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # Account protection
    LOGIN_MAX_ATTEMPTS: int = 5            # failed logins before lockout
    LOGIN_LOCKOUT_MINUTES: int = 15        # lockout duration after threshold
    REQUIRE_EMAIL_VERIFICATION: bool = False  # enforced for sensitive actions when true
    PASSWORD_MIN_LENGTH: int = 12
    MFA_ISSUER: str = "Saha"               # label shown in authenticator apps
    REQUIRE_ADMIN_MFA: bool = True         # admins without a second factor are refused
    REQUIRE_STEP_UP_AUTH: bool = True      # re-auth for money movement + vault egress

    # Open Innovation Library weekly digest ("N new open resources this week").
    # Runs in-process in every worker; a Postgres advisory lock serializes the
    # send. Set LIBRARY_DIGEST_ENABLED=false to silence it entirely.
    LIBRARY_DIGEST_ENABLED: bool = True
    LIBRARY_DIGEST_INTERVAL_DAYS: int = 7

    # End-to-end chat is handled by Matrix/Element, never server-side decryption.
    MATRIX_HOMESERVER_URL: str = ""
    MATRIX_SERVER_NAME: str = ""
    MATRIX_SERVICE_USER_ID: str = ""
    MATRIX_SERVICE_ACCESS_TOKEN: str = ""
    ELEMENT_WEB_URL: str = ""

    # Request body caps (bytes) — enforced by the size-guard middleware
    MAX_JSON_BODY_BYTES: int = 1_000_000       # 1 MB for JSON/API bodies
    MAX_UPLOAD_BYTES: int = 52_428_800         # 50 MB for multipart uploads (vault assets)

    # Cookie-based auth (Phase 2). When true, refresh tokens are set as
    # httpOnly cookies and CSRF double-submit is enforced on unsafe methods.
    COOKIE_AUTH_ENABLED: bool = True
    COOKIE_DOMAIN: str = ""                # e.g. ".sahasolutions.com" in prod; empty = host-only
    COOKIE_SECURE: bool = False            # set true in production (HTTPS only)

    # CORS
    CORS_ORIGINS: list[str] = ["http://localhost:3000"]

    # Public URL of the web app — used to build email links (verification, etc.)
    FRONTEND_URL: str = "http://localhost:3000"

    # Reverse-proxy chain. Forwarding headers are honoured ONLY when the socket
    # peer falls inside one of these networks; see app/core/clientip.py.
    TRUSTED_PROXY_CIDRS: list[str] = ["127.0.0.1/32", "::1/128"]
    TRUSTED_CLIENT_IP_HEADER: str = "CF-Connecting-IP"

    # Persona KYC
    PERSONA_API_KEY: str = ""
    PERSONA_WEBHOOK_SECRET: str = ""
    PERSONA_TEMPLATE_ID: str = ""
    KYC_MOCK_MODE: bool = True

    # Stripe
    STRIPE_SECRET_KEY: str = ""
    STRIPE_WEBHOOK_SECRET: str = ""

    # DocuSign
    DOCUSIGN_ACCOUNT_ID: str = ""
    DOCUSIGN_INTEGRATION_KEY: str = ""
    DOCUSIGN_PRIVATE_KEY: str = ""

    # Encryption. V2 is the write key; V1 is retained only so objects encrypted
    # before the rotation remain readable. See app/services/vault.py.
    VAULT_ENCRYPTION_KEY: str = "change-me-32-bytes-in-production!"
    VAULT_ENCRYPTION_KEY_V2: str = ""
    # Set true ONLY while the rotation backfill is outstanding.
    #
    # The V1 key found in production was the placeholder published in the git
    # repository, so every object wrapped under it must be treated as having
    # been stored in cleartext. Deleting it outright would make those objects
    # unreadable, so it stays configured until scripts/rotate_vault_key.py has
    # re-wrapped everything — but that is a compromised state, and it must be
    # acknowledged deliberately rather than tolerated silently. Boot logs a
    # warning on every startup while this is true.
    VAULT_V1_ROTATION_PENDING: bool = False

    # Hosts allowed to reach the API (["*"] disables the check — dev only)
    ALLOWED_HOSTS: list[str] = ["*"]

    @property
    def is_production(self) -> bool:
        return self.APP_ENV is AppEnv.PRODUCTION

    @property
    def is_internet_facing(self) -> bool:
        """Staging holds the same data on the same network as production, so it
        gets the same hardening. Only development is exempt."""
        return self.APP_ENV in (AppEnv.STAGING, AppEnv.PRODUCTION)

    @property
    def allows_mock_integrations(self) -> bool:
        """Mock KYC and mock payments are development-only, full stop.

        Previously these were gated on standalone flags (KYC_MOCK_MODE, an empty
        Stripe key), which meant an internet-facing deployment could — and did —
        run with a self-approving identity check and a payment step that moved no
        money (SAHA-004, SAHA-036)."""
        return self.APP_ENV is AppEnv.DEVELOPMENT


_INSECURE_DEFAULTS = {
    "SECRET_KEY": ("change-me-in-production", "dev-secret-key-change-in-production"),
    "VAULT_ENCRYPTION_KEY": ("change-me-32-bytes-in-production!", "dev-vault-key-32-bytes-padding!!"),
    "VAULT_ENCRYPTION_KEY_V2": ("change-me-32-bytes-in-production!", "dev-vault-key-32-bytes-padding!!"),
    "MINIO_ACCESS_KEY": ("minioadmin",),
    "MINIO_SECRET_KEY": ("minioadmin",),
}


def validate_security_critical(s: "Settings") -> list[str]:
    """Fatal in EVERY environment, including development.

    Key material is the one class of setting where a placeholder is never
    acceptable: the vault key was found in production set to the literal
    placeholder from .env.example, a value published in the git repository
    (security/AUDIT.md SAHA-001). A guard that only runs in production would
    not have caught it, because the deployment was labelled `staging`.
    """
    problems = []
    for field, bad_values in _INSECURE_DEFAULTS.items():
        value = getattr(s, field)
        if not value or value not in bad_values:
            continue
        # The one permitted exception: a compromised V1 key may remain
        # configured while the rotation backfill runs, but only when a strong V2
        # key is in place and the state has been explicitly acknowledged.
        if (
            field == "VAULT_ENCRYPTION_KEY"
            and s.VAULT_V1_ROTATION_PENDING
            and s.VAULT_ENCRYPTION_KEY_V2
            and s.VAULT_ENCRYPTION_KEY_V2 not in _INSECURE_DEFAULTS["VAULT_ENCRYPTION_KEY_V2"]
        ):
            continue
        problems.append(f"{field} is set to a known development default")

    if s.VAULT_ENCRYPTION_KEY_V2 and len(s.VAULT_ENCRYPTION_KEY_V2) < 32:
        problems.append("VAULT_ENCRYPTION_KEY_V2 must be at least 32 characters")
    if s.VAULT_V1_ROTATION_PENDING and not s.VAULT_ENCRYPTION_KEY_V2:
        problems.append(
            "VAULT_V1_ROTATION_PENDING is set but VAULT_ENCRYPTION_KEY_V2 is not — "
            "there is nothing to rotate to"
        )
    return problems


def rotation_warnings(s: "Settings") -> list[str]:
    """Non-fatal states that must be visible on every boot, not just once."""
    warnings = []
    if s.VAULT_V1_ROTATION_PENDING:
        warnings.append(
            "VAULT KEY ROTATION OUTSTANDING: objects still encrypted under the v1 key "
            "are readable with a key published in this repository. Run "
            "`uv run python scripts/rotate_vault_key.py --apply`, then clear both "
            "VAULT_ENCRYPTION_KEY and VAULT_V1_ROTATION_PENDING."
        )
    return warnings


def validate_production_settings(s: "Settings") -> list[str]:
    """Fatal misconfigurations for any internet-facing deployment."""
    problems = validate_security_critical(s)
    if not s.is_internet_facing:
        return problems
    if s.DEBUG:
        problems.append("DEBUG must be false outside development")
    if s.KYC_MOCK_MODE:
        problems.append("KYC_MOCK_MODE must be false outside development")
    if "*" in s.ALLOWED_HOSTS:
        problems.append("ALLOWED_HOSTS must list explicit hostnames outside development")
    if any(o.startswith("http://") for o in s.CORS_ORIGINS):
        problems.append("CORS_ORIGINS must not contain plaintext http:// origins")
    if s.COOKIE_AUTH_ENABLED and not s.COOKIE_SECURE:
        problems.append("COOKIE_SECURE must be true outside development (HTTPS-only cookies)")
    if not s.VAULT_ENCRYPTION_KEY_V2:
        problems.append("VAULT_ENCRYPTION_KEY_V2 must be set (vault key rotation)")
    if s.FRONTEND_URL.startswith("http://localhost"):
        problems.append("FRONTEND_URL still points at localhost — email links will be broken")
    if s.SMTP_HOST not in ("localhost", "127.0.0.1") and not s.SMTP_USE_TLS:
        problems.append("SMTP_USE_TLS must be true when using a remote mail server")
    if s.ALLOW_EXTERNAL_LLM_FOR_CONFIDENTIAL:
        problems.append(
            "ALLOW_EXTERNAL_LLM_FOR_CONFIDENTIAL sends trade-secret content to a "
            "third-party inference API; requires a signed DPA and a documented transfer basis"
        )
    return problems


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
