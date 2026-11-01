import enum
import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, Enum as SAEnum, ForeignKey, Integer, Numeric, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class MaterialStatus(str, enum.Enum):
    ACTIVE = "active"
    PAUSED = "paused"
    ARCHIVED = "archived"


class RawMaterialListing(Base):
    """Secondary marketplace: raw materials a seller can supply in their region.

    Lets IP buyers procure production inputs locally (cost) and line up backup
    suppliers (resilience). Any verified marketplace user can sell.
    """

    __tablename__ = "raw_material_listings"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    seller_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    category: Mapped[str] = mapped_column(String(100), nullable=False)
    region: Mapped[str] = mapped_column(String(100), nullable=False)
    country: Mapped[str] = mapped_column(String(100), nullable=False)
    unit: Mapped[str] = mapped_column(String(50), nullable=False)
    price_per_unit: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="USD")
    min_order_quantity: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    monthly_capacity: Mapped[str | None] = mapped_column(String(255))
    lead_time_days: Mapped[int | None] = mapped_column(Integer)
    status: Mapped[MaterialStatus] = mapped_column(
        SAEnum(MaterialStatus, name="material_status", create_type=False,
               values_callable=lambda obj: [e.value for e in obj]),
        nullable=False,
        default=MaterialStatus.ACTIVE,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
