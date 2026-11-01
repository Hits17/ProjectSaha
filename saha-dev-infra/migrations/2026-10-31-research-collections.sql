-- Requires the existing users/open_resources schema. All collections are private.
BEGIN;
CREATE TABLE IF NOT EXISTS research_collections (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    owner_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name VARCHAR(120) NOT NULL,
    description TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_research_collections_owner ON research_collections(owner_id, created_at);
CREATE TABLE IF NOT EXISTS research_collection_items (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    collection_id UUID NOT NULL REFERENCES research_collections(id) ON DELETE CASCADE,
    resource_id UUID NOT NULL REFERENCES open_resources(id) ON DELETE CASCADE,
    note TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_collection_resource UNIQUE(collection_id,resource_id)
);
CREATE INDEX IF NOT EXISTS ix_research_collection_items_collection ON research_collection_items(collection_id, created_at);
CREATE TABLE IF NOT EXISTS saved_research_searches (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    owner_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    label VARCHAR(120) NOT NULL,
    query VARCHAR(255) NOT NULL,
    resource_type VARCHAR(20) NOT NULL DEFAULT '' CHECK (resource_type IN ('','patent','research_paper','trademark')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_owner_research_search UNIQUE(owner_id,query,resource_type)
);
CREATE INDEX IF NOT EXISTS ix_saved_research_search_owner ON saved_research_searches(owner_id, created_at);
GRANT SELECT, INSERT, UPDATE, DELETE ON research_collections, research_collection_items, saved_research_searches TO saha;
COMMIT;
