import enum
import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean, DateTime, Enum as SAEnum, ForeignKey, Integer, Numeric,
    String, Text, UniqueConstraint, func,
)
from sqlalchemy.dialects.postgresql import ARRAY, INET, JSON, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


class TransactionStatus(str, enum.Enum):
    PENDING_LEGAL = "pending_legal"
    CONTRACT_DRAFTING = "contract_drafting"
    CONTRACT_REVIEW = "contract_review"
    SIGNING_PENDING = "signing_pending"
    SIGNED = "signed"
    ESCROW_PENDING = "escrow_pending"
    ESCROW_FUNDED = "escrow_funded"
    DISBURSEMENT_PENDING = "disbursement_pending"
    COMPLETED = "completed"
    DISPUTED = "disputed"
    CANCELLED = "cancelled"


class LawFirmPartner(Base):
    __tablename__ = "law_firm_partners"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    jurisdictions: Mapped[list[str]] = mapped_column(ARRAY(String), server_default="{}", nullable=False)
    contact_email: Mapped[str | None] = mapped_column(String(255))
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class Transaction(Base):
    __tablename__ = "transactions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    proposal_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("proposals.id"), nullable=False)
    listing_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("ip_listings.id"), nullable=False)
    buyer_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    seller_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    law_firm_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("law_firm_partners.id"))
    status: Mapped[TransactionStatus] = mapped_column(
        SAEnum(TransactionStatus, name="transaction_status", create_type=False,
               values_callable=lambda obj: [e.value for e in obj]),
        nullable=False,
        default=TransactionStatus.PENDING_LEGAL,
    )
    deal_value_usd: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False)
    saha_commission_usd: Mapped[Decimal | None] = mapped_column(Numeric(15, 2))
    legal_fee_usd: Mapped[Decimal | None] = mapped_column(Numeric(15, 2))
    escrow_fee_usd: Mapped[Decimal | None] = mapped_column(Numeric(15, 2))
    deal_summary: Mapped[dict | None] = mapped_column(JSON)
    contract_docusign_envelope_id: Mapped[str | None] = mapped_column(String(255))
    contract_storage_key: Mapped[str | None] = mapped_column(String(1000))
    # Contracts are now encrypted at rest like vault assets, and their plaintext
    # digest is recorded so a signature can be bound to specific bytes and
    # post-hoc substitution is detectable (security/AUDIT.md SAHA-021).
    contract_sha256: Mapped[str | None] = mapped_column(String(64))
    contract_encryption_key_id: Mapped[str | None] = mapped_column(String(8))
    stripe_payment_intent_id: Mapped[str | None] = mapped_column(String(255))
    escrow_funded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    disbursed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    law_firm: Mapped[LawFirmPartner | None] = relationship("LawFirmPartner")
    disbursements: Mapped[list["Disbursement"]] = relationship(
        "Disbursement", back_populates="transaction", cascade="all, delete-orphan"
    )
    signatures: Mapped[list["ContractSignature"]] = relationship(
        "ContractSignature", back_populates="transaction", cascade="all, delete-orphan"
    )


class ContractSignature(Base):
    """One party's execution of a specific contract.

    Previously `POST /sign` flipped the transaction to SIGNED when *either*
    party called it, recorded nothing about who signed, and left the DocuSign
    envelope id permanently NULL — so a party could deny having agreed and
    nothing in the system contradicted them (security/AUDIT.md SAHA-008).

    `contract_sha256` binds the signature to the exact bytes signed. If the
    stored contract is later replaced, verification fails rather than silently
    passing, which is the whole point of holding the digest here rather than
    trusting the object store.
    """

    __tablename__ = "contract_signatures"
    __table_args__ = (UniqueConstraint("transaction_id", "signer_id", name="uq_contract_signer"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    transaction_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("transactions.id", ondelete="CASCADE"), nullable=False
    )
    signer_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    contract_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    ip_address: Mapped[str | None] = mapped_column(INET)
    user_agent: Mapped[str | None] = mapped_column(Text)
    signed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    transaction: Mapped["Transaction"] = relationship("Transaction", back_populates="signatures")


class Disbursement(Base):
    __tablename__ = "disbursements"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    transaction_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("transactions.id"), nullable=False
    )
    ip_holder_amount_usd: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False)
    saha_commission_usd: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False)
    legal_fee_usd: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False)
    escrow_fee_usd: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False)
    stripe_transfer_ids: Mapped[dict | None] = mapped_column(JSON)
    # Who authorised the release, and why. Escrow release is irreversible; an
    # unattributed disbursement row cannot answer "who decided this?" in a
    # dispute (security/AUDIT.md SAHA-007).
    released_by_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    release_reason: Mapped[str | None] = mapped_column(String(500))
    executed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    transaction: Mapped["Transaction"] = relationship("Transaction", back_populates="disbursements")
