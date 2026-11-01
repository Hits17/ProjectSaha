import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field

from app.db.models.user import KYCStatus, UserRole


class PlatformStats(BaseModel):
    users_total: int
    users_by_role: dict[str, int]
    listings_total: int
    listings_by_status: dict[str, int]
    proposals_total: int
    proposals_by_status: dict[str, int]
    transactions_total: int
    transactions_by_status: dict[str, int]
    reviews_total: int
    total_disbursed_usd: float
    total_commission_usd: float
    pipeline_value_usd: float


class AdminUserRow(BaseModel):
    id: uuid.UUID
    email: str
    full_name: str
    role: str
    kyc_status: str
    is_active: bool
    created_at: datetime
    model_config = {"from_attributes": True}


class AuditLogRow(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID | None
    action: str
    resource_type: str | None
    resource_id: uuid.UUID | None
    created_at: datetime
    model_config = {"from_attributes": True}


class AdminUserDetail(BaseModel):
    user: AdminUserRow
    listings_count: int
    proposals_count: int
    transactions_count: int
    average_rating: float | None
    review_count: int
    recent_audit: list[AuditLogRow]


class AdminTransactionRow(BaseModel):
    id: uuid.UUID
    status: str
    deal_value_usd: float
    saha_commission_usd: float | None = None
    buyer_id: uuid.UUID
    seller_id: uuid.UUID
    listing_id: uuid.UUID | None = None
    escrow_funded_at: datetime | None = None
    disbursed_at: datetime | None = None
    created_at: datetime
    updated_at: datetime
    model_config = {"from_attributes": True}


class AdminListingRow(BaseModel):
    id: uuid.UUID
    title: str
    status: str
    product_category: str | None
    view_count: int
    creator_id: uuid.UUID
    creator_email: str
    created_at: datetime
    updated_at: datetime


class AdminProposalRow(BaseModel):
    id: uuid.UUID
    listing_id: uuid.UUID
    listing_title: str
    buyer_id: uuid.UUID
    seller_id: uuid.UUID
    status: str
    offer_amount_usd: float | None
    version: int
    created_at: datetime
    updated_at: datetime


class AdminReviewRow(BaseModel):
    id: uuid.UUID
    transaction_id: uuid.UUID
    reviewer_id: uuid.UUID
    reviewee_id: uuid.UUID
    rating: int
    comment: str | None
    created_at: datetime
    model_config = {"from_attributes": True}


class LawFirmRow(BaseModel):
    id: uuid.UUID
    name: str
    jurisdictions: list[str]
    contact_email: str | None
    is_active: bool
    created_at: datetime
    model_config = {"from_attributes": True}


class DisbursementRow(BaseModel):
    id: uuid.UUID
    transaction_id: uuid.UUID
    ip_holder_amount_usd: Decimal
    saha_commission_usd: Decimal
    legal_fee_usd: Decimal
    escrow_fee_usd: Decimal
    executed_at: datetime | None
    created_at: datetime
    model_config = {"from_attributes": True}


# ── Request bodies ───────────────────────────────────────────────────────────

class SetActiveRequest(BaseModel):
    is_active: bool


class SetRoleRequest(BaseModel):
    role: UserRole


class SetKYCRequest(BaseModel):
    kyc_status: KYCStatus
    reason: str = Field(..., min_length=3, max_length=500)


class ResolveDisputeRequest(BaseModel):
    resolution: str = Field(..., pattern="^(complete|cancel)$")
    reason: str = Field(..., min_length=3, max_length=500)


class CreateLawFirmRequest(BaseModel):
    name: str = Field(..., min_length=2, max_length=255)
    jurisdictions: list[str] = []
    contact_email: str | None = None


class UpdateLawFirmRequest(BaseModel):
    name: str | None = Field(None, min_length=2, max_length=255)
    jurisdictions: list[str] | None = None
    contact_email: str | None = None
    is_active: bool | None = None
