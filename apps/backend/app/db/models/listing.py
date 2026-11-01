import enum
import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger, Boolean, DateTime, Enum as SAEnum, ForeignKey,
    Integer, Numeric, String, Text, func,
)
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


class ListingStatus(str, enum.Enum):
    DRAFT = "draft"
    AI_GENERATING = "ai_generating"
    REVIEW = "review"
    PUBLISHED = "published"
    ARCHIVED = "archived"


class IPListing(Base):
    __tablename__ = "ip_listings"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    creator_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    product_category: Mapped[str | None] = mapped_column(String(255))
    tags: Mapped[list[str]] = mapped_column(ARRAY(String), server_default="{}", nullable=False)
    equipment_requirements: Mapped[list[str]] = mapped_column(ARRAY(String), server_default="{}", nullable=False)
    batch_size_definition: Mapped[str | None] = mapped_column(String(500))
    public_description: Mapped[str | None] = mapped_column(Text)
    status: Mapped[ListingStatus] = mapped_column(
        SAEnum(ListingStatus, name="listing_status", create_type=False,
               values_callable=lambda obj: [e.value for e in obj]),
        nullable=False,
        default=ListingStatus.DRAFT,
    )
    view_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    qdrant_point_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    bom_items: Mapped[list["BOMItem"]] = relationship(
        "BOMItem", back_populates="listing", cascade="all, delete-orphan"
    )
    vault_assets: Mapped[list["IPVaultAsset"]] = relationship(
        "IPVaultAsset", back_populates="listing", cascade="all, delete-orphan"
    )


class BOMItem(Base):
    __tablename__ = "bom_items"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    listing_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ip_listings.id", ondelete="CASCADE"), nullable=False
    )
    material_name: Mapped[str] = mapped_column(String(255), nullable=False)
    specification: Mapped[str | None] = mapped_column(Text)
    quantity_per_unit: Mapped[Decimal] = mapped_column(Numeric(15, 6), nullable=False)
    unit_of_measure: Mapped[str] = mapped_column(String(50), nullable=False)
    shelf_life_days: Mapped[int | None] = mapped_column(Integer)
    procurement_cadence: Mapped[str | None] = mapped_column(String(20))
    is_critical: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    listing: Mapped["IPListing"] = relationship("IPListing", back_populates="bom_items")


class IPVaultAsset(Base):
    __tablename__ = "ip_vault_assets"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    listing_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ip_listings.id", ondelete="CASCADE"), nullable=False
    )
    storage_key: Mapped[str] = mapped_column(String(1000), nullable=False)
    original_filename: Mapped[str] = mapped_column(String(500), nullable=False)
    file_size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    content_type: Mapped[str | None] = mapped_column(String(255))
    # Which vault key version encrypted this object. Was always "v1" and never
    # read; now it selects the decryption key, which is what makes rotation
    # possible at all (security/AUDIT.md SAHA-001).
    encryption_key_id: Mapped[str] = mapped_column(String(255), nullable=False)
    # SHA-256 of the plaintext at ingest — lets a later read prove the bytes
    # returned are the bytes that were uploaded.
    content_sha256: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    listing: Mapped["IPListing"] = relationship("IPListing", back_populates="vault_assets")
