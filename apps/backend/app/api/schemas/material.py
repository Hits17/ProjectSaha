import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field, field_validator

from app.db.models.material import MaterialStatus

MATERIAL_CATEGORIES = {
    "metals",
    "polymers_plastics",
    "textiles",
    "wood_paper",
    "chemicals",
    "electronics_components",
    "ceramics_glass",
    "packaging",
    "agricultural",
    "other",
}


class MaterialCreate(BaseModel):
    title: str = Field(min_length=3, max_length=255)
    description: str | None = Field(default=None, max_length=5000)
    category: str
    region: str = Field(min_length=2, max_length=100)
    country: str = Field(min_length=2, max_length=100)
    unit: str = Field(min_length=1, max_length=50)
    price_per_unit: Decimal = Field(gt=0, le=Decimal("9999999999"))
    currency: str = Field(default="USD", min_length=3, max_length=3)
    min_order_quantity: Decimal | None = Field(default=None, gt=0)
    monthly_capacity: str | None = Field(default=None, max_length=255)
    lead_time_days: int | None = Field(default=None, ge=0, le=365)

    @field_validator("category")
    @classmethod
    def _valid_category(cls, v: str) -> str:
        if v not in MATERIAL_CATEGORIES:
            raise ValueError(f"category must be one of: {', '.join(sorted(MATERIAL_CATEGORIES))}")
        return v

    @field_validator("currency")
    @classmethod
    def _upper_currency(cls, v: str) -> str:
        return v.upper()


class MaterialUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=3, max_length=255)
    description: str | None = Field(default=None, max_length=5000)
    category: str | None = None
    region: str | None = Field(default=None, min_length=2, max_length=100)
    country: str | None = Field(default=None, min_length=2, max_length=100)
    unit: str | None = Field(default=None, min_length=1, max_length=50)
    price_per_unit: Decimal | None = Field(default=None, gt=0, le=Decimal("9999999999"))
    currency: str | None = Field(default=None, min_length=3, max_length=3)
    min_order_quantity: Decimal | None = Field(default=None, gt=0)
    monthly_capacity: str | None = Field(default=None, max_length=255)
    lead_time_days: int | None = Field(default=None, ge=0, le=365)
    status: MaterialStatus | None = None

    @field_validator("category")
    @classmethod
    def _valid_category(cls, v: str | None) -> str | None:
        if v is not None and v not in MATERIAL_CATEGORIES:
            raise ValueError(f"category must be one of: {', '.join(sorted(MATERIAL_CATEGORIES))}")
        return v

    @field_validator("currency")
    @classmethod
    def _upper_currency(cls, v: str | None) -> str | None:
        return v.upper() if v else v


class MaterialResponse(BaseModel):
    id: uuid.UUID
    seller_id: uuid.UUID
    title: str
    description: str | None
    category: str
    region: str
    country: str
    unit: str
    price_per_unit: Decimal
    currency: str
    min_order_quantity: Decimal | None
    monthly_capacity: str | None
    lead_time_days: int | None
    status: MaterialStatus
    created_at: datetime
    updated_at: datetime
    # Seller display name only. The email was previously returned on every
    # browse row, which handed any verified member the platform's contact
    # directory 100 rows at a time — while the negotiation channel spends real
    # effort blocking parties from exchanging exactly that (security/AUDIT.md
    # SAHA-016). Contact happens through the platform, not through a list view.
    seller_name: str | None = None
    model_config = {"from_attributes": True}
