-- =============================================================================
-- Social feed, voting, standing and profiles — 2026-08-06
--
-- Design: docs/SOCIAL-FEED-DESIGN.md
--
-- Two decisions encoded in this schema are easy to undo by accident:
--
--   1. user_standing (social) is SEPARATE from transaction reviews (track
--      record) and there is no column anywhere that sums them. Standing is
--      cheap to earn; a completed deal is not. Merging them would let someone
--      farm engagement and arrive at a negotiation looking like a proven
--      counterparty.
--
--   2. posts.visibility defaults to 'members', not 'public'. Premature public
--      disclosure destroys patent novelty permanently, so broadcasting to the
--      open internet is a choice a member makes, never one they inherit.
--
-- IDEMPOTENT: safe to re-run.
--
-- RUN AS: postgres (CREATE TYPE and table ownership).
--   sudo -u postgres psql -d saha -f /tmp/saha-social.sql
-- =============================================================================

BEGIN;

-- ── Enums ───────────────────────────────────────────────────────────────────

DO $$ BEGIN
    CREATE TYPE post_visibility AS ENUM ('public', 'members', 'community');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
    CREATE TYPE post_kind AS ENUM ('update', 'question', 'showcase');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
    CREATE TYPE vote_target AS ENUM ('post', 'comment');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;


-- ── Posts ───────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS posts (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    author_id           UUID NOT NULL REFERENCES users(id),
    visibility          post_visibility NOT NULL DEFAULT 'members',
    community_id        UUID REFERENCES communities(id) ON DELETE CASCADE,
    kind                post_kind NOT NULL DEFAULT 'update',
    title               VARCHAR(300),
    body                TEXT NOT NULL,
    link_url            VARCHAR(1000),
    listing_id          UUID REFERENCES ip_listings(id) ON DELETE SET NULL,
    resource_id         UUID REFERENCES open_resources(id) ON DELETE SET NULL,
    score               INTEGER NOT NULL DEFAULT 0,
    up_count            INTEGER NOT NULL DEFAULT 0,
    down_count          INTEGER NOT NULL DEFAULT 0,
    comment_count       INTEGER NOT NULL DEFAULT 0,
    -- Reddit's hot ordering, stored so the feed sorts in the database.
    hot_rank            DOUBLE PRECISION NOT NULL DEFAULT 0,
    -- True when the disclosure classifier fired and the author published anyway.
    -- Kept for the evidence trail; not shown to other members.
    disclosure_flagged  BOOLEAN NOT NULL DEFAULT FALSE,
    edited_at           TIMESTAMPTZ,
    deleted_at          TIMESTAMPTZ,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_posts_hot        ON posts (hot_rank DESC) WHERE deleted_at IS NULL;
CREATE INDEX IF NOT EXISTS ix_posts_author     ON posts (author_id, created_at DESC);
CREATE INDEX IF NOT EXISTS ix_posts_community  ON posts (community_id) WHERE community_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS ix_posts_visibility ON posts (visibility, created_at DESC);


-- ── Comments ────────────────────────────────────────────────────────────────
-- One level of threading. Deeper nesting is where discussion quality degrades on
-- a network this size; the depth limit is enforced in the service layer.

CREATE TABLE IF NOT EXISTS post_comments (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    post_id     UUID NOT NULL REFERENCES posts(id) ON DELETE CASCADE,
    author_id   UUID NOT NULL REFERENCES users(id),
    parent_id   UUID REFERENCES post_comments(id) ON DELETE CASCADE,
    body        TEXT NOT NULL,
    score       INTEGER NOT NULL DEFAULT 0,
    up_count    INTEGER NOT NULL DEFAULT 0,
    down_count  INTEGER NOT NULL DEFAULT 0,
    -- Wilson score lower bound at 80% confidence (Reddit's "best" sort).
    confidence  DOUBLE PRECISION NOT NULL DEFAULT 0,
    edited_at   TIMESTAMPTZ,
    deleted_at  TIMESTAMPTZ,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_comments_post   ON post_comments (post_id, confidence DESC);
CREATE INDEX IF NOT EXISTS ix_comments_author ON post_comments (author_id);


-- ── Votes ───────────────────────────────────────────────────────────────────
-- Attributable, not fuzzed. Reddit randomises displayed counts to deny bot
-- operators a feedback signal — sound on an anonymous platform. Saha is
-- KYC-verified with an append-only audit log, so fuzzing would only make the
-- numbers untrustworthy. The unique constraint is the real defence.

CREATE TABLE IF NOT EXISTS votes (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    voter_id    UUID NOT NULL REFERENCES users(id),
    target_type vote_target NOT NULL,
    target_id   UUID NOT NULL,
    value       INTEGER NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_vote_once  UNIQUE (voter_id, target_type, target_id),
    CONSTRAINT ck_vote_value CHECK (value IN (-1, 1))
);

CREATE INDEX IF NOT EXISTS ix_votes_target ON votes (target_type, target_id);


-- ── Profiles (self-asserted) ────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS user_profiles (
    user_id     UUID PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    headline    VARCHAR(220),      -- LinkedIn's limit
    about       VARCHAR(2600),     -- LinkedIn's limit
    location    VARCHAR(120),
    website_url VARCHAR(500),
    skills      TEXT[] NOT NULL DEFAULT '{}',
    experience  JSONB,
    featured    JSONB,
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);


-- ── Standing (derived social reputation) ────────────────────────────────────
-- No column here combines with transaction reputation, and none should be added.

CREATE TABLE IF NOT EXISTS user_standing (
    user_id          UUID PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    post_standing    BIGINT NOT NULL DEFAULT 0,
    comment_standing BIGINT NOT NULL DEFAULT 0,
    total_standing   BIGINT NOT NULL DEFAULT 0,
    posts_count      INTEGER NOT NULL DEFAULT 0,
    comments_count   INTEGER NOT NULL DEFAULT 0,
    computed_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_standing_total ON user_standing (total_standing DESC);


-- ── Follows and saves ───────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS follows (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    follower_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    followee_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_follow_once   UNIQUE (follower_id, followee_id),
    CONSTRAINT ck_no_self_follow CHECK (follower_id <> followee_id)
);

CREATE INDEX IF NOT EXISTS ix_follows_follower ON follows (follower_id);
CREATE INDEX IF NOT EXISTS ix_follows_followee ON follows (followee_id);

CREATE TABLE IF NOT EXISTS saved_posts (
    id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id    UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    post_id    UUID NOT NULL REFERENCES posts(id) ON DELETE CASCADE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_saved_once UNIQUE (user_id, post_id)
);

CREATE INDEX IF NOT EXISTS ix_saved_user ON saved_posts (user_id, created_at DESC);


-- ── Grants ──────────────────────────────────────────────────────────────────
-- The application role needs ordinary DML on the new tables. Note it is NOT
-- granted anything on audit_logs beyond SELECT/INSERT — see the 2026-08-05
-- migration.

GRANT SELECT, INSERT, UPDATE, DELETE ON
    posts, post_comments, votes, user_profiles, user_standing, follows, saved_posts
TO saha;

COMMIT;
