-- =============================================================================
-- Security hardening migration — 2026-08-05
--
-- Companion to the audit in security/AUDIT.md. Covers:
--   SAHA-001  vault key versioning + content digests
--   SAHA-007  attribution on escrow release
--   SAHA-008  dual-signature contract execution
--   SAHA-014  tamper-evident, append-only audit log
--   SAHA-021  contract integrity digest
--   SAHA-030  TOTP replay guard
--   SAHA-037  single-execution exclusivity per listing
--
-- IDEMPOTENT: safe to re-run. Every statement is guarded.
--
-- ORDERING NOTE (see memory: known_fixes) — the enum/type-owning statements and
-- the GRANT/REVOKE block must run as the OWNER of the objects. Run the whole file
-- as the `saha` role except the clearly marked SUPERUSER section at the end:
--
--   psql -U saha  -d saha -f 2026-08-05-security-hardening.sql
--   psql -U postgres -d saha -c "\i ...superuser section..."   -- see notes below
-- =============================================================================

BEGIN;

-- ── SAHA-001: vault key versioning + integrity digests ──────────────────────
-- `encryption_key_id` already existed but was always 'v1' and never read. It now
-- selects the decryption key, which is what makes rotation possible at all.
ALTER TABLE ip_vault_assets
    ADD COLUMN IF NOT EXISTS content_sha256 VARCHAR(64);

-- Negotiation messages are encrypted with the same key, so they need the same
-- version marker — without it, rotating would make every stored message
-- permanently unreadable.
ALTER TABLE messages
    ADD COLUMN IF NOT EXISTS encryption_key_id VARCHAR(8) NOT NULL DEFAULT 'v1';


-- ── SAHA-021: contract integrity ────────────────────────────────────────────
ALTER TABLE transactions
    ADD COLUMN IF NOT EXISTS contract_sha256 VARCHAR(64),
    ADD COLUMN IF NOT EXISTS contract_encryption_key_id VARCHAR(8);


-- ── SAHA-007: escrow release attribution ────────────────────────────────────
-- An unattributed disbursement row cannot answer "who decided this?" in a
-- dispute — and escrow release is irreversible.
ALTER TABLE disbursements
    ADD COLUMN IF NOT EXISTS released_by_id UUID REFERENCES users(id),
    ADD COLUMN IF NOT EXISTS release_reason VARCHAR(500);


-- ── SAHA-030: TOTP replay guard ─────────────────────────────────────────────
ALTER TABLE users
    ADD COLUMN IF NOT EXISTS mfa_last_counter BIGINT;


-- ── SAHA-008: dual-signature contract execution ─────────────────────────────
-- `contract_sha256` binds a signature to the exact bytes signed, so a contract
-- replaced after execution fails verification rather than passing silently.
CREATE TABLE IF NOT EXISTS contract_signatures (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    transaction_id   UUID NOT NULL REFERENCES transactions(id) ON DELETE CASCADE,
    signer_id        UUID NOT NULL REFERENCES users(id),
    contract_sha256  VARCHAR(64) NOT NULL,
    ip_address       INET,
    user_agent       TEXT,
    signed_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_contract_signer UNIQUE (transaction_id, signer_id)
);

CREATE INDEX IF NOT EXISTS ix_contract_signatures_txn
    ON contract_signatures (transaction_id);


-- ── SAHA-037: one executed deal per listing ─────────────────────────────────
-- IP is not fungible: two buyers cannot both acquire the same exclusive right.
-- The service layer checks this under a row lock (assert_no_competing_deal);
-- this partial unique index is the backstop that holds even if a code path
-- forgets to.
--
-- The index is created conditionally rather than unconditionally, because a
-- database that ALREADY violates the invariant is exactly what this finding
-- predicts — and it turned out to be true here on the first run: listing
-- fb037599 carried three executed deals, two of them completed and disbursed,
-- all typed "Exclusive" for the same territory and duration.
--
-- Aborting the whole migration over pre-existing data would hold every other
-- fix hostage to a data-cleanup decision that belongs to an operator, not to a
-- schema script. Rewriting those rows automatically would be worse: they are
-- financial and evidentiary records, and a migration must not quietly edit
-- transaction history to make a constraint fit.
--
-- So: create the index when the data permits, and report precisely what blocks
-- it when it does not. Exclusivity is still enforced for every NEW deal by the
-- service-layer check. Re-run this file after resolving the conflicts and the
-- index will be created.
DO $$
DECLARE
    conflicts TEXT;
    n INT;
BEGIN
    SELECT count(*), string_agg(listing_id::text || ' (' || cnt || ' deals)', ', ')
      INTO n, conflicts
      FROM (
        SELECT listing_id, count(*) AS cnt
          FROM transactions
         WHERE status IN ('signed', 'escrow_pending', 'escrow_funded',
                          'disbursement_pending', 'completed')
         GROUP BY listing_id
        HAVING count(*) > 1
      ) dupes;

    IF n = 0 THEN
        CREATE UNIQUE INDEX IF NOT EXISTS uq_listing_single_executed_deal
            ON transactions (listing_id)
            WHERE status IN ('signed', 'escrow_pending', 'escrow_funded',
                             'disbursement_pending', 'completed');
        RAISE NOTICE 'SAHA-037: exclusivity index created.';
    ELSE
        RAISE WARNING E'\n'
            '=====================================================================\n'
            'SAHA-037: exclusivity index NOT created — % listing(s) already have\n'
            'more than one executed deal:\n'
            '  %\n'
            '\n'
            'This is the double-sale condition the audit describes, present in\n'
            'existing data. New deals ARE blocked by the service-layer check that\n'
            'ships with this migration; these historical rows are not touched.\n'
            '\n'
            'To inspect:\n'
            '  SELECT id, status, deal_value_usd, created_at FROM transactions\n'
            '   WHERE listing_id = ''<id>'' ORDER BY created_at;\n'
            '\n'
            'Resolve deliberately (cancel the superseded deals, or accept them as\n'
            'test artefacts and delete them), then re-run this file to create the\n'
            'index. See security/AUDIT.md SAHA-037.\n'
            '=====================================================================',
            n, conflicts;
    END IF;
END $$;


-- ── SAHA-014: tamper-evident audit log ──────────────────────────────────────
-- entry_hash = SHA-256( prev_hash || canonical(payload) )
-- Altering, deleting or reordering any row breaks every subsequent hash.
-- Columns are nullable so pre-migration rows stay valid; the verifier treats the
-- first hashed row as the chain root.
CREATE SEQUENCE IF NOT EXISTS audit_logs_seq_seq;

ALTER TABLE audit_logs
    ADD COLUMN IF NOT EXISTS seq        BIGINT,
    ADD COLUMN IF NOT EXISTS prev_hash  VARCHAR(64),
    ADD COLUMN IF NOT EXISTS entry_hash VARCHAR(64);

-- Backfill seq for existing rows in creation order, then make it mandatory.
UPDATE audit_logs SET seq = nextval('audit_logs_seq_seq')
    WHERE seq IS NULL;

ALTER TABLE audit_logs
    ALTER COLUMN seq SET DEFAULT nextval('audit_logs_seq_seq');

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'uq_audit_logs_seq'
    ) THEN
        ALTER TABLE audit_logs ADD CONSTRAINT uq_audit_logs_seq UNIQUE (seq);
    END IF;
END $$;

ALTER TABLE audit_logs ALTER COLUMN seq SET NOT NULL;
ALTER SEQUENCE audit_logs_seq_seq OWNED BY audit_logs.seq;

CREATE INDEX IF NOT EXISTS ix_audit_logs_seq ON audit_logs (seq);


-- Append-only enforcement. The hash chain makes tampering *detectable*; this
-- makes it *fail*. Both are needed: the trigger stops the ordinary case, the
-- chain survives someone with enough privilege to drop the trigger.
CREATE OR REPLACE FUNCTION audit_logs_append_only()
RETURNS TRIGGER AS $$
BEGIN
    RAISE EXCEPTION
        'audit_logs is append-only: % is not permitted (security/AUDIT.md SAHA-014)',
        TG_OP;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_audit_logs_append_only ON audit_logs;
CREATE TRIGGER trg_audit_logs_append_only
    BEFORE UPDATE OR DELETE ON audit_logs
    FOR EACH ROW EXECUTE FUNCTION audit_logs_append_only();


-- ── Performance indexes for the new access patterns ─────────────────────────
CREATE INDEX IF NOT EXISTS ix_transactions_listing_status
    ON transactions (listing_id, status);

CREATE INDEX IF NOT EXISTS ix_demand_signals_created_at
    ON demand_signals (created_at DESC);

COMMIT;


-- =============================================================================
-- SUPERUSER SECTION — run separately as `postgres`.
--
--   psql -U postgres -d saha -f - <<'SQL'
--   ... the block below ...
--   SQL
--
-- Least privilege on the evidentiary table (SAHA-014, SAHA-034). The trigger
-- above already refuses UPDATE/DELETE; revoking the grant means the attempt is
-- refused one layer earlier and cannot be re-enabled by dropping a trigger the
-- app role owns.
--
-- REVOKE UPDATE, DELETE, TRUNCATE ON audit_logs FROM saha;
-- GRANT  SELECT, INSERT ON audit_logs TO saha;
--
-- Deliberately NOT applied automatically: revoking privileges on a live system
-- while the previous release is still running would break its audit writes.
-- Apply after the new backend is deployed and verified.
-- =============================================================================
