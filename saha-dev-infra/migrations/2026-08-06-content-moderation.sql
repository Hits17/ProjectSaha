-- =============================================================================
-- Content safety moderation — 2026-08-06
--
-- Companion to the social feed migration. Adds the moderation pipeline:
-- classifier verdicts on posts, a member reporting table, and the review state
-- an admin acts on.
--
-- Design note worth keeping in the schema itself: a post is only visible when
-- moderation_status is 'published', 'flagged' or 'approved'. The classifier can
-- move a post INTO 'held'; only an admin review moves it out. That asymmetry is
-- deliberate — the cost of a wrongly-held post is a delay, the cost of a
-- wrongly-published one may not be recoverable.
--
-- IDEMPOTENT: safe to re-run.
-- RUN AS: postgres (CREATE TYPE + table ownership).
-- =============================================================================

BEGIN;

DO $$ BEGIN
    CREATE TYPE moderation_status AS ENUM
        ('published', 'flagged', 'held', 'approved', 'rejected', 'removed');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
    CREATE TYPE report_reason AS ENUM
        ('harmful', 'illegal', 'harassment', 'spam', 'confidential', 'other');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;


-- ── Moderation state on posts ───────────────────────────────────────────────

ALTER TABLE posts
    ADD COLUMN IF NOT EXISTS moderation_status  moderation_status NOT NULL DEFAULT 'published',
    ADD COLUMN IF NOT EXISTS safety_categories  TEXT[] NOT NULL DEFAULT '{}',
    ADD COLUMN IF NOT EXISTS safety_reason      VARCHAR(500),
    ADD COLUMN IF NOT EXISTS held_at            TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS reviewed_by        UUID REFERENCES users(id),
    ADD COLUMN IF NOT EXISTS reviewed_at        TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS review_note        VARCHAR(1000),
    ADD COLUMN IF NOT EXISTS report_count       INTEGER NOT NULL DEFAULT 0;

-- The feed filters on this constantly; the review queue reads the complement.
CREATE INDEX IF NOT EXISTS ix_posts_moderation
    ON posts (moderation_status) WHERE deleted_at IS NULL;

-- Review queue: oldest held first. A queue is a FIFO, not a feed — someone whose
-- legitimate post was held should not wait behind newer arrivals.
CREATE INDEX IF NOT EXISTS ix_posts_review_queue
    ON posts (held_at ASC NULLS LAST)
    WHERE moderation_status IN ('held', 'flagged');


-- ── Member reports ──────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS content_reports (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    reporter_id UUID NOT NULL REFERENCES users(id),
    target_type vote_target NOT NULL,
    target_id   UUID NOT NULL,
    reason      report_reason NOT NULL,
    detail      VARCHAR(1000),
    resolved_at TIMESTAMPTZ,
    resolved_by UUID REFERENCES users(id),
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    -- One report per member per item. Without this a single member could
    -- manufacture the appearance of consensus by reporting repeatedly.
    CONSTRAINT uq_report_once UNIQUE (reporter_id, target_type, target_id)
);

CREATE INDEX IF NOT EXISTS ix_reports_target
    ON content_reports (target_type, target_id) WHERE resolved_at IS NULL;
CREATE INDEX IF NOT EXISTS ix_reports_open
    ON content_reports (created_at DESC) WHERE resolved_at IS NULL;

GRANT SELECT, INSERT, UPDATE, DELETE ON content_reports TO saha;

COMMIT;
