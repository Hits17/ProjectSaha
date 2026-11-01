"""
Regression suite for SAHA-014 — the audit log was append-only by convention only.

`audit_logs` was an ordinary table owned by the same Postgres role the
application uses for everything else: no REVOKE, no trigger, no hash chain, no
signatures, no external anchor. `UPDATE` and `DELETE` both succeeded, so any
operator — or anyone with a restored backup — could rewrite history undetectably.

Saha's stated purpose is to record and evidence transactions that lawyers rely
on. An evidentiary layer anyone can rewrite does not support that, which is why
this ranked above several findings with higher CVSS scores.

Canonical serialisation is the load-bearing part. Non-canonical JSON hashing
silently destroys verifiability: the same event serialised twice yields
different digests and every check fails for reasons nobody can diagnose.
`log_metadata` is free-form JSONB, so this is not theoretical.
"""

import pytest
import uuid
from datetime import datetime, timedelta, timezone

from app.core.audit import _hashed_payload, canonical, compute_entry_hash, verify_chain


class _Entry:
    """Stand-in for an AuditLog row — verify_chain reads attributes only."""

    def __init__(self, seq, action, user_id=None, resource_type=None,
                 resource_id=None, created_at=None, metadata=None):
        self.seq = seq
        self.action = action
        self.user_id = user_id
        self.resource_type = resource_type
        self.resource_id = resource_id
        self.created_at = created_at or datetime(2026, 1, 1, tzinfo=timezone.utc)
        self.log_metadata = metadata
        self.prev_hash = None
        self.entry_hash = None


def _chain(entries):
    prev = None
    for e in entries:
        payload = _hashed_payload(
            e.action, e.user_id, e.resource_type, e.resource_id, e.created_at, e.log_metadata
        )
        e.prev_hash = prev
        e.entry_hash = compute_entry_hash(prev, payload)
        prev = e.entry_hash
    return entries


# ── Canonical serialisation ─────────────────────────────────────────────────

def test_canonical_is_key_order_independent():
    assert canonical({"a": 1, "b": 2}) == canonical({"b": 2, "a": 1})


def test_canonical_is_stable_across_nesting():
    assert canonical({"x": {"p": 1, "q": 2}}) == canonical({"x": {"q": 2, "p": 1}})


def test_canonical_has_no_insignificant_whitespace():
    assert b" " not in canonical({"a": 1, "b": 2})


def test_canonical_handles_non_json_types():
    """Must never raise mid-write — a serialisation error would silently drop
    an audit entry, which is the failure this whole module exists to prevent."""
    value = canonical({"id": uuid.uuid4(), "when": datetime.now(timezone.utc)})
    assert isinstance(value, bytes) and value


def test_canonical_preserves_unicode_rather_than_escaping():
    assert "é".encode() in canonical({"name": "café"})


# ── Chain verification ──────────────────────────────────────────────────────

def test_intact_chain_verifies():
    ok, bad = verify_chain(_chain([_Entry(1, "a"), _Entry(2, "b"), _Entry(3, "c")]))
    assert ok and bad is None


def test_mutated_action_is_detected():
    entries = _chain([_Entry(1, "user.login"), _Entry(2, "vault.file_downloaded"), _Entry(3, "user.logout")])
    entries[1].action = "user.login"          # attacker hides a vault download
    ok, bad = verify_chain(entries)
    assert not ok and bad == 2


def test_mutated_metadata_is_detected():
    entries = _chain([_Entry(1, "a", metadata={"amount": 100}), _Entry(2, "b")])
    entries[0].log_metadata = {"amount": 1}
    ok, bad = verify_chain(entries)
    assert not ok and bad == 1


def test_backdated_timestamp_is_detected():
    entries = _chain([_Entry(1, "a"), _Entry(2, "b")])
    entries[1].created_at = entries[1].created_at - timedelta(days=30)
    ok, bad = verify_chain(entries)
    assert not ok and bad == 2


def test_deleted_entry_is_detected():
    entries = _chain([_Entry(1, "a"), _Entry(2, "b"), _Entry(3, "c")])
    ok, bad = verify_chain([entries[0], entries[2]])   # middle row removed
    assert not ok and bad == 3


def test_reordered_entries_are_detected():
    entries = _chain([_Entry(1, "a"), _Entry(2, "b"), _Entry(3, "c")])
    ok, _ = verify_chain([entries[0], entries[2], entries[1]])
    assert not ok


def test_forged_entry_appended_without_the_chain_is_detected():
    entries = _chain([_Entry(1, "a"), _Entry(2, "b")])
    forged = _Entry(3, "admin.user_role_changed")
    forged.prev_hash = "0" * 64
    forged.entry_hash = "f" * 64
    ok, bad = verify_chain(entries + [forged])
    assert not ok and bad == 3


def test_prehash_rows_are_skipped_not_failed():
    """Rows written before the chain existed carry NULL hashes and must not
    invalidate the chain that starts after them."""
    legacy = _Entry(1, "old.action")             # prev_hash / entry_hash stay None
    ok, _ = verify_chain([legacy] + _chain([_Entry(2, "a"), _Entry(3, "b")]))
    assert ok


# ── Privacy: what the chain covers ──────────────────────────────────────────

def test_hashed_payload_excludes_erasable_personal_data():
    """Immutability and erasure rights have to coexist (ROADMAP §6). Only a
    pseudonymous subject id and a metadata digest are made permanent; IP
    address, user agent and the raw metadata body stay erasable."""
    payload = _hashed_payload(
        "user.login", uuid.uuid4(), "user", uuid.uuid4(),
        datetime.now(timezone.utc), {"email": "someone@example.com"},
    )
    assert set(payload) == {
        "action", "subject", "resource_type", "resource_id", "occurred_at", "metadata_sha256"
    }
    assert "someone@example.com" not in str(payload)
    assert "ip_address" not in payload and "user_agent" not in payload


# ── Round-trip through a real database ──────────────────────────────────────
#
# The tests above verify the chain logic over in-memory objects, and they all
# passed while the live chain was silently unverifiable: `created_at` has
# server_default=now(), so letting the database populate it stored a different
# timestamp from the one that went into the hash. Verification recomputed over
# the stored value and failed every time.
#
# Nothing that operates on hand-constructed objects can catch that. Only a
# write-then-read round-trip against Postgres can, which is what this does.

@pytest.mark.requires_db
@pytest.mark.anyio
async def test_write_then_verify_roundtrip():
    """Write real entries through write_audit_log, read them back, verify."""
    import uuid as _uuid

    from sqlalchemy import select

    from app.core.audit import write_audit_log
    from app.db.models.audit_log import AuditLog
    from app.db.session import AsyncSessionLocal

    marker = f"test.roundtrip.{_uuid.uuid4().hex[:8]}"
    for i in range(3):
        await write_audit_log(
            action=marker,
            resource_type="probe",
            metadata={"i": i, "nested": {"b": 2, "a": 1}},
        )

    async with AsyncSessionLocal() as db:
        rows = (await db.execute(
            select(AuditLog).order_by(AuditLog.seq)
        )).scalars().all()

    written = [r for r in rows if r.action == marker]
    assert len(written) == 3, "entries were not persisted"
    assert all(r.entry_hash for r in written), "entries were not hashed"

    # Verify from this test's first entry onward. Earlier rows may include ones
    # written by a defective build, and an append-only table cannot be corrected
    # after the fact — see verify_chain's `since_seq`.
    ok, bad_seq = verify_chain(rows, since_seq=written[0].seq)
    assert ok, (
        f"chain does not verify against the stored rows (first bad seq: {bad_seq}). "
        "The hashed payload must be reproducible from what is actually persisted."
    )


@pytest.mark.requires_db
@pytest.mark.anyio
async def test_stored_created_at_is_the_hashed_timestamp():
    """The precise invariant the round-trip failure came down to."""
    import uuid as _uuid

    from sqlalchemy import select

    from app.core.audit import compute_entry_hash, write_audit_log
    from app.db.models.audit_log import AuditLog
    from app.db.session import AsyncSessionLocal

    marker = f"test.timestamp.{_uuid.uuid4().hex[:8]}"
    await write_audit_log(action=marker, resource_type="probe", metadata={"x": 1})

    async with AsyncSessionLocal() as db:
        row = (await db.execute(
            select(AuditLog).where(AuditLog.action == marker)
        )).scalar_one()

    recomputed = compute_entry_hash(
        row.prev_hash,
        _hashed_payload(row.action, row.user_id, row.resource_type,
                        row.resource_id, row.created_at, row.log_metadata),
    )
    assert recomputed == row.entry_hash, (
        "entry_hash cannot be reproduced from the stored row — created_at is "
        "not the instant that was hashed"
    )
