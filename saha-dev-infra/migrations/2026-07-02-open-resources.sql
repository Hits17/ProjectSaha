-- Migration: Open Innovation Library — admin-curated open-source patents &
-- research papers members can build on royalty-free (2026-07-02)
-- Apply to an existing database:
--   psql "postgresql://saha:<password>@localhost:5432/saha" -f 2026-07-02-open-resources.sql
-- Fresh installs get this automatically via init-scripts/01-schema.sql.

CREATE TYPE open_resource_type AS ENUM ('patent', 'research_paper');

CREATE TABLE IF NOT EXISTS open_resources (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    resource_type open_resource_type NOT NULL,
    title VARCHAR(300) NOT NULL,
    summary TEXT,
    authors VARCHAR(500),
    organization VARCHAR(255),
    identifier VARCHAR(120),              -- patent number or DOI
    source_url VARCHAR(1000) NOT NULL,
    license VARCHAR(120) NOT NULL,        -- e.g. 'Public domain (expired patent)', 'CC BY 4.0'
    category VARCHAR(100),                -- R&D domain, mirrors community topics
    tags TEXT[] NOT NULL DEFAULT '{}',
    published_year INTEGER,
    is_active BOOLEAN NOT NULL DEFAULT true,
    view_count INTEGER NOT NULL DEFAULT 0,
    added_by UUID NOT NULL REFERENCES users(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Browse queries filter by type/category on active rows, newest first.
CREATE INDEX IF NOT EXISTS idx_open_resources_active_created
    ON open_resources (is_active, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_open_resources_type ON open_resources (resource_type);
CREATE INDEX IF NOT EXISTS idx_open_resources_category ON open_resources (category);
