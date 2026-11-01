-- Migration: social — IP R&D communities + group chat (2026-06-18)
-- Apply to an existing database:
--   psql "postgresql://saha:<password>@localhost:5432/saha" -f 2026-06-18-social-communities.sql
-- Fresh installs get this automatically via init-scripts/01-schema.sql.

CREATE TYPE community_visibility AS ENUM ('public', 'private');
CREATE TYPE membership_role AS ENUM ('owner', 'moderator', 'member');

CREATE TABLE communities (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(120) NOT NULL,
    slug VARCHAR(140) UNIQUE NOT NULL,
    description TEXT,
    topic VARCHAR(80) NOT NULL,
    visibility community_visibility NOT NULL DEFAULT 'public',
    created_by UUID NOT NULL REFERENCES users(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_communities_topic ON communities(topic);
CREATE INDEX idx_communities_visibility ON communities(visibility);
CREATE INDEX idx_communities_created_by ON communities(created_by);

CREATE TABLE community_memberships (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    community_id UUID NOT NULL REFERENCES communities(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES users(id),
    role membership_role NOT NULL DEFAULT 'member',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_community_member UNIQUE (community_id, user_id)
);

CREATE INDEX idx_memberships_community ON community_memberships(community_id);
CREATE INDEX idx_memberships_user ON community_memberships(user_id);

CREATE TABLE community_messages (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    community_id UUID NOT NULL REFERENCES communities(id) ON DELETE CASCADE,
    sender_id UUID NOT NULL REFERENCES users(id),
    content TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_community_messages_community ON community_messages(community_id, created_at);
