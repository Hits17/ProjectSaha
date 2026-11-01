import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field


class CreateProposalRequest(BaseModel):
    listing_id: uuid.UUID
    offer_amount_usd: Decimal | None = None
    license_type: str | None = None
    territory: str | None = None
    duration_months: int | None = None


class SubmitProposalRequest(BaseModel):
    offer_amount_usd: Decimal = Field(..., gt=0)
    license_type: str = Field(..., min_length=1, max_length=100)
    territory: str = Field(..., min_length=1, max_length=255)
    duration_months: int = Field(..., gt=0)
    notes: str | None = None


class CounterOfferRequest(BaseModel):
    offer_amount_usd: Decimal = Field(..., gt=0)
    license_type: str = Field(..., min_length=1, max_length=100)
    territory: str = Field(..., min_length=1, max_length=255)
    duration_months: int = Field(..., gt=0)
    notes: str | None = None


class SendMessageRequest(BaseModel):
    content: str = Field(..., min_length=1, max_length=5000)


class ProposalVersionResponse(BaseModel):
    id: uuid.UUID
    version: int
    offer_amount_usd: Decimal | None
    license_type: str | None
    territory: str | None
    duration_months: int | None
    proposed_by_id: uuid.UUID
    notes: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class MessageResponse(BaseModel):
    id: uuid.UUID
    sender_id: uuid.UUID
    content: str
    is_blocked: bool
    block_reason: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class ProposalResponse(BaseModel):
    id: uuid.UUID
    listing_id: uuid.UUID
    buyer_id: uuid.UUID
    seller_id: uuid.UUID
    status: str
    offer_amount_usd: Decimal | None
    license_type: str | None
    territory: str | None
    duration_months: int | None
    nda_signed_at: datetime | None
    version: int
    versions: list[ProposalVersionResponse] = []
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
