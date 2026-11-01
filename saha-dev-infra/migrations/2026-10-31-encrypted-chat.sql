-- Apply after 2026-10-31-open-collaboration.sql. Never rewrites old messages.
BEGIN;
CREATE TABLE IF NOT EXISTS chat_identities (
    user_id UUID PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    matrix_user_id VARCHAR(255) NOT NULL UNIQUE,
    linked_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS encrypted_chat_rooms (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    scope VARCHAR(20) NOT NULL CHECK (scope IN ('community', 'proposal', 'transaction')),
    scope_id UUID NOT NULL,
    matrix_room_id VARCHAR(255) NOT NULL UNIQUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_encrypted_chat_scope UNIQUE(scope, scope_id)
);
GRANT SELECT, INSERT, UPDATE, DELETE ON chat_identities, encrypted_chat_rooms TO saha;
COMMIT;
