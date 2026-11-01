import enum
import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import Boolean, DateTime, Enum as SAEnum, ForeignKey, Integer, LargeBinary, Numeric, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


class ProposalStatus(str, enum.Enum):
    DRAFT = "draft"
    SUBMITTED = "submitted"
    NDA_PENDING = "nda_pending"
    NDA_SIGNED = "nda_signed"
    NEGOTIATING = "negotiating"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    WITHDRAWN = "withdrawn"


class Proposal(Base):
    __tablename__ = "proposals"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    listing_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("ip_listings.id"), nullable=False)
    buyer_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    seller_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    status: Mapped[ProposalStatus] = mapped_column(
        SAEnum(ProposalStatus, name="proposal_status", create_type=False,
               values_callable=lambda obj: [e.value for e in obj]),
        nullable=False,
        default=ProposalStatus.DRAFT,
    )
    offer_amount_usd: Mapped[Decimal | None] = mapped_column(Numeric(15, 2))
    license_type: Mapped[str | None] = mapped_column(String(100))
    territory: Mapped[str | None] = mapped_column(String(255))
    duration_months: Mapped[int | None] = mapped_column(Integer)
    ai_draft_used: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    nda_docusign_envelope_id: Mapped[str | None] = mapped_column(String(255))
    nda_signed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    versions: Mapped[list["ProposalVersion"]] = relationship(
        "ProposalVersion", back_populates="proposal", cascade="all, delete-orphan", order_by="ProposalVersion.version"
    )
    messages: Mapped[list["Message"]] = relationship(
        "Message", back_populates="proposal", cascade="all, delete-orphan", order_by="Message.created_at"
    )


class ProposalVersion(Base):
    __tablename__ = "proposal_versions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    proposal_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("proposals.id", ondelete="CASCADE"), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    offer_amount_usd: Mapped[Decimal | None] = mapped_column(Numeric(15, 2))
    license_type: Mapped[str | None] = mapped_column(String(100))
    territory: Mapped[str | None] = mapped_column(String(255))
    duration_months: Mapped[int | None] = mapped_column(Integer)
    proposed_by_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    proposal: Mapped["Proposal"] = relationship("Proposal", back_populates="versions")


class Message(Base):
    __tablename__ = "messages"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    proposal_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("proposals.id", ondelete="CASCADE"), nullable=False)
    sender_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    encrypted_content: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    # Vault key version this message was encrypted under — see services/vault.py.
    encryption_key_id: Mapped[str] = mapped_column(String(8), nullable=False, server_default="v1")
    is_blocked: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    block_reason: Mapped[str | None] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    proposal: Mapped["Proposal"] = relationship("Proposal", back_populates="messages")
