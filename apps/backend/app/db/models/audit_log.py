import uuid
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Sequence, String, Text, func
from sqlalchemy.dialects.postgresql import INET, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base

_audit_seq = Sequence("audit_logs_seq_seq")


class AuditLog(Base):
    """Append-only record of every material act on the platform.

    Saha's purpose is to record, evidence and facilitate transactions whose
    legal effect happens at a registry and whose handover is run by lawyers. An
    audit trail any operator can rewrite undetectably does not support that
    (security/AUDIT.md SAHA-014), so entries are now chained:

        entry_hash = SHA-256( prev_hash || canonical(payload) )

    Verification walks the chain and recomputes each digest. Altering, deleting
    or reordering any row breaks every subsequent hash — which makes tampering
    *detectable* rather than merely discouraged. Enforcement (REVOKE
    UPDATE/DELETE plus a trigger, and a separate INSERT-only role) is applied in
    the migration; the chain is what survives a compromise of that enforcement.

    `seq` gives the chain a total order that does not depend on timestamp
    collisions. Personal data is deliberately kept OUT of the hashed payload —
    only pseudonymous ids and content digests are covered — so that erasure
    rights and evidentiary immutability can coexist (ROADMAP §6).
    """

    __tablename__ = "audit_logs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    seq: Mapped[int] = mapped_column(
        BigInteger, _audit_seq, server_default=_audit_seq.next_value(), unique=True, nullable=False
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    action: Mapped[str] = mapped_column(String(100), nullable=False)
    resource_type: Mapped[str | None] = mapped_column(String(100))
    resource_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    ip_address: Mapped[str | None] = mapped_column(INET)
    user_agent: Mapped[str | None] = mapped_column(Text)
    ai_provider: Mapped[str | None] = mapped_column(String(50))
    log_metadata: Mapped[dict | None] = mapped_column("metadata", JSONB)

    # Tamper-evidence chain. Nullable so pre-migration rows remain valid; the
    # verifier treats the first hashed row as the chain root.
    prev_hash: Mapped[str | None] = mapped_column(String(64))
    entry_hash: Mapped[str | None] = mapped_column(String(64))

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
