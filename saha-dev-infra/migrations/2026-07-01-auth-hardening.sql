-- Migration: enterprise auth hardening — account lockout, email verification, TOTP MFA (2026-07-01)
-- Apply to an existing database:
--   psql "postgresql://saha:<password>@localhost:5432/saha" -f 2026-07-01-auth-hardening.sql
-- Fresh installs get this automatically via init-scripts/01-schema.sql.
--
-- Idempotent: uses IF NOT EXISTS so re-running is safe.

ALTER TABLE users ADD COLUMN IF NOT EXISTS failed_login_attempts INTEGER NOT NULL DEFAULT 0;
ALTER TABLE users ADD COLUMN IF NOT EXISTS locked_until TIMESTAMPTZ;
ALTER TABLE users ADD COLUMN IF NOT EXISTS email_verified BOOLEAN NOT NULL DEFAULT false;
ALTER TABLE users ADD COLUMN IF NOT EXISTS email_verified_at TIMESTAMPTZ;
ALTER TABLE users ADD COLUMN IF NOT EXISTS mfa_enabled BOOLEAN NOT NULL DEFAULT false;
ALTER TABLE users ADD COLUMN IF NOT EXISTS mfa_secret VARCHAR(255);

-- Existing accounts predate email verification. Treat them as already-verified
-- so the (opt-in) enforcement doesn't lock out current users on rollout.
UPDATE users SET email_verified = true, email_verified_at = NOW()
WHERE email_verified = false AND created_at < NOW();
