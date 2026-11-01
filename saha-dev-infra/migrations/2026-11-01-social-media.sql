-- Additive social-media release. Apply as the schema owner after the October migrations.
BEGIN;
CREATE TABLE IF NOT EXISTS post_media (
    id UUID PRIMARY KEY,
    owner_id UUID NOT NULL REFERENCES users(id),
    post_id UUID REFERENCES posts(id) ON DELETE CASCADE,
    storage_key VARCHAR(500) NOT NULL UNIQUE,
    content_type VARCHAR(80) NOT NULL,
    byte_size INTEGER NOT NULL CHECK (byte_size > 0 AND byte_size <= 41943040),
    alt_text VARCHAR(500) NOT NULL DEFAULT '',
    position INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_post_media_owner_id ON post_media(owner_id);
CREATE INDEX IF NOT EXISTS ix_post_media_post_id ON post_media(post_id);
CREATE TABLE IF NOT EXISTS post_reactions (
    post_id UUID NOT NULL REFERENCES posts(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    kind VARCHAR(20) NOT NULL CONSTRAINT ck_post_reaction_kind CHECK (kind IN ('like','celebrate','support','love','insightful','curious')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY(post_id,user_id)
);
GRANT SELECT, INSERT, UPDATE, DELETE ON post_media, post_reactions TO saha;
COMMIT;
