-- Migration: user profile pictures (2026-07-02)
-- Apply to an existing database:
--   psql "postgresql://saha:<password>@localhost:5432/saha" -f 2026-07-02-user-avatars.sql
-- Fresh installs get this automatically via init-scripts/01-schema.sql.
-- Note: ALTER TABLE users may require the table owner (sudo -u postgres psql).

-- MinIO object key of the user's profile picture (avatars/<user_id>/<uuid>.<ext>).
-- Stored unencrypted (unlike vault assets) and served through the authenticated
-- GET /api/v1/users/{id}/avatar endpoint.
ALTER TABLE users ADD COLUMN IF NOT EXISTS avatar_key VARCHAR(500);
