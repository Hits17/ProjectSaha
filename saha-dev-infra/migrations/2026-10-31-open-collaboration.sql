-- Requires all migrations through 2026-08-06-social-feed/content-moderation.
-- Additive migration; no legacy message or transaction data is rewritten.
BEGIN;

ALTER TABLE communities ADD COLUMN IF NOT EXISTS is_institution BOOLEAN NOT NULL DEFAULT FALSE;
ALTER TABLE communities ADD COLUMN IF NOT EXISTS website_url VARCHAR(1000);
ALTER TABLE communities ADD COLUMN IF NOT EXISTS verification_status VARCHAR(20) NOT NULL DEFAULT 'unverified';
DO $$ BEGIN
    ALTER TABLE communities ADD CONSTRAINT ck_space_verification
        CHECK (verification_status IN ('unverified', 'pending', 'verified', 'rejected'));
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

CREATE TABLE IF NOT EXISTS space_private_records (
    community_id UUID PRIMARY KEY REFERENCES communities(id) ON DELETE CASCADE,
    reference VARCHAR(40) NOT NULL UNIQUE,
    request_note TEXT,
    evidence_url VARCHAR(1000),
    review_note TEXT,
    reviewed_by UUID REFERENCES users(id),
    requested_at TIMESTAMPTZ,
    reviewed_at TIMESTAMPTZ
);
INSERT INTO space_private_records (community_id, reference)
SELECT id, 'SP-' || upper(replace(gen_random_uuid()::text, '-', '')) FROM communities
ON CONFLICT (community_id) DO NOTHING;

CREATE TABLE IF NOT EXISTS platform_policy (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    institution_verification_enabled BOOLEAN NOT NULL DEFAULT FALSE,
    updated_by UUID REFERENCES users(id),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
INSERT INTO platform_policy (id) VALUES (1) ON CONFLICT (id) DO NOTHING;
CREATE INDEX IF NOT EXISTS ix_communities_institutions ON communities (is_institution, verification_status, created_at);
GRANT SELECT, INSERT, UPDATE, DELETE ON space_private_records, platform_policy TO saha;
COMMIT;
