-- Migration: in-app notifications + real-time (SSE) feed (2026-07-01)
-- Apply to an existing database:
--   psql "postgresql://saha:<password>@localhost:5432/saha" -f 2026-07-01-notifications.sql
-- Fresh installs get this automatically via init-scripts/01-schema.sql.

CREATE TABLE IF NOT EXISTS notifications (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id),
    type VARCHAR(64) NOT NULL,
    title VARCHAR(255) NOT NULL,
    body TEXT,
    link VARCHAR(512),
    is_read BOOLEAN NOT NULL DEFAULT false,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Unread-count and per-user feed queries hit (user_id, is_read) and (user_id, created_at).
CREATE INDEX IF NOT EXISTS idx_notifications_user_unread ON notifications (user_id, is_read);
CREATE INDEX IF NOT EXISTS idx_notifications_user_created ON notifications (user_id, created_at DESC);
