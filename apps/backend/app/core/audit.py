"""
Tamper-evident audit logging.

Every entry is chained to its predecessor:

    entry_hash = SHA-256( prev_hash || canonical(payload) )

Two properties make this actually verifiable rather than decorative:

**Canonical serialisation.** `canonical()` produces one byte sequence for one
logical payload — sorted keys, no insignificant whitespace, UTF-8, explicit null
handling. Non-canonical JSON hashing silently destroys verifiability: the same
event serialised twice yields different digests and every check fails for
reasons nobody can diagnose. `log_metadata` is free-form JSONB, so this is not
a theoretical concern.

**PII stays out of the hashed payload.** The chain covers action, pseudonymous
subject id, resource, timestamp and a digest of the metadata — not the metadata
itself, and never raw IP, user agent or email. Those live in ordinary columns
that can be erased on request without breaking the chain, which is how erasure
rights and evidentiary immutability coexist (ROADMAP §6).

See security/AUDIT.md SAHA-014.
"""

import hashlib
import json
import uuid
from datetime import datetime, timezone
from typing import Any, Iterable

import structlog
from sqlalchemy import select

from app.db.models.audit_log import AuditLog

logger = structlog.get_logger()


def canonical(payload: Any) -> bytes:
    """Deterministic byte representation of a JSON-compatible value.

    RFC 8785-style: keys sorted, separators fixed, no ASCII escaping, and every
    non-JSON type coerced through `str` so serialisation can never fail
    mid-write and silently drop an audit entry.
    """
    return json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        default=str,
    ).encode("utf-8")


def _hashed_payload(
    action: str,
    user_id: uuid.UUID | None,
    resource_type: str | None,
    resource_id: uuid.UUID | None,
    occurred_at: datetime,
    metadata: dict | None,
) -> dict:
    """The subset of the entry covered by the chain.

    Deliberately excludes ip_address, user_agent and the raw metadata body:
    those are erasable personal data. The metadata is bound by digest, so its
    contents are still provable if retained, without being immortalised.
    """
    return {
        "action": action,
        "subject": str(user_id) if user_id else None,
        "resource_type": resource_type,
        "resource_id": str(resource_id) if resource_id else None,
        "occurred_at": occurred_at.astimezone(timezone.utc).isoformat(),
        "metadata_sha256": hashlib.sha256(canonical(metadata or {})).hexdigest(),
    }


def compute_entry_hash(prev_hash: str | None, payload: dict) -> str:
    return hashlib.sha256((prev_hash or "").encode() + canonical(payload)).hexdigest()


async def write_audit_log(
    action: str,
    user_id: uuid.UUID | None = None,
    resource_type: str | None = None,
    resource_id: uuid.UUID | None = None,
    ip_address: str | None = None,
    user_agent: str | None = None,
    ai_provider: str | None = None,
    metadata: dict | None = None,
) -> None:
    """Write one chained audit entry in a fresh session.

    Runs as a BackgroundTask, so it must never raise into the request path — but
    a *silently* lost audit entry is its own problem, so failures are logged
    loudly rather than swallowed.
    """
    from app.db.session import AsyncSessionLocal

    occurred_at = datetime.now(timezone.utc)
    payload = _hashed_payload(action, user_id, resource_type, resource_id, occurred_at, metadata)

    try:
        async with AsyncSessionLocal() as db:
            # Serialise chain appends so two concurrent writers cannot both read
            # the same tip and fork the chain. The lock is transaction-scoped and
            # released on commit.
            from sqlalchemy import text as _text
            await db.execute(_text("SELECT pg_advisory_xact_lock(hashtext('saha.audit_chain'))"))

            prev_hash = await db.scalar(
                select(AuditLog.entry_hash)
                .where(AuditLog.entry_hash.isnot(None))
                .order_by(AuditLog.seq.desc())
                .limit(1)
            )
            db.add(
                AuditLog(
                    user_id=user_id,
                    action=action,
                    resource_type=resource_type,
                    resource_id=resource_id,
                    ip_address=ip_address,
                    user_agent=user_agent,
                    ai_provider=ai_provider,
                    log_metadata=metadata,
                    # created_at MUST be the same instant that went into the hash.
                    # The column has server_default=now(), so letting the database
                    # populate it stores a DIFFERENT timestamp from the one hashed
                    # — and verification then recomputes over the stored value and
                    # fails every time. The chain looks healthy (hashes are being
                    # written) while being silently unverifiable, which is the
                    # exact failure this module's docstring warns about. Caught by
                    # test_write_then_verify_roundtrip.
                    created_at=occurred_at,
                    prev_hash=prev_hash,
                    entry_hash=compute_entry_hash(prev_hash, payload),
                )
            )
            await db.commit()
    except Exception as exc:  # noqa: BLE001 — a lost audit entry must be visible
        logger.error("audit_write_failed", action=action, error=str(exc))


def verify_chain(
    entries: Iterable[AuditLog], since_seq: int | None = None
) -> tuple[bool, int | None]:
    """Recompute the chain over `entries`, ordered by seq ascending.

    Returns (ok, first_bad_seq). Rows written before the chain existed carry a
    NULL entry_hash and are skipped; the first hashed row considered is treated
    as the chain root.

    `since_seq` declares where the verified chain begins. It exists because a
    chain can acquire a permanently unverifiable row: the table is append-only,
    so a row written by a defective build cannot be corrected or removed. An
    operator must then be able to state "the chain is verified from seq N" and
    have that be checkable, rather than the whole history reading as broken
    forever.

    That is a deliberate escape hatch and it is auditable in itself — moving the
    genesis forward is a recorded configuration change, not something the code
    does on its own. It must never be used to skip past inconvenient rows.
    """
    prev: str | None = None
    started = False
    for entry in entries:
        if entry.entry_hash is None:
            continue
        if since_seq is not None and entry.seq < since_seq:
            continue
        payload = _hashed_payload(
            entry.action,
            entry.user_id,
            entry.resource_type,
            entry.resource_id,
            entry.created_at,
            entry.log_metadata,
        )
        if started and entry.prev_hash != prev:
            return False, entry.seq
        if compute_entry_hash(entry.prev_hash, payload) != entry.entry_hash:
            return False, entry.seq
        prev = entry.entry_hash
        started = True
    return True, None
