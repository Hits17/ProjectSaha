-- Migration: Open Innovation Library v2 — member submissions (admin approval)
-- and "I'm building this" declarations (2026-07-02, second pass)
-- Apply to an existing database:
--   psql "postgresql://saha:<password>@localhost:5432/saha" -f 2026-07-02-open-library-v2.sql
-- Fresh installs get this automatically via init-scripts/01-schema.sql.

-- Member-submitted resources enter as 'pending' and appear publicly only once
-- an admin approves. Rows admins create directly are 'approved' from birth.
CREATE TYPE open_resource_status AS ENUM ('pending', 'approved', 'rejected');
ALTER TABLE open_resources
    ADD COLUMN IF NOT EXISTS status open_resource_status NOT NULL DEFAULT 'approved';

-- Public "I'm building this" declarations: social proof + the engagement metric
-- (resources → active builds → listings derived from them).
CREATE TABLE IF NOT EXISTS open_resource_builds (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    resource_id UUID NOT NULL REFERENCES open_resources(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES users(id),
    note VARCHAR(500),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (resource_id, user_id)
);

CREATE INDEX IF NOT EXISTS idx_open_resource_builds_resource
    ON open_resource_builds (resource_id);
CREATE INDEX IF NOT EXISTS idx_open_resources_status ON open_resources (status);
