import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field


class LawFirmResponse(BaseModel):
    id: uuid.UUID
    name: str
    jurisdictions: list[str]
    contact_email: str | None
    model_config = {"from_attributes": True}


class DisbursementResponse(BaseModel):
    id: uuid.UUID
    ip_holder_amount_usd: Decimal
    saha_commission_usd: Decimal
    legal_fee_usd: Decimal
    escrow_fee_usd: Decimal
    executed_at: datetime | None
    created_at: datetime
    model_config = {"from_attributes": True}


class TransactionResponse(BaseModel):
    id: uuid.UUID
    proposal_id: uuid.UUID
    listing_id: uuid.UUID
    buyer_id: uuid.UUID
    seller_id: uuid.UUID
    status: str
    deal_value_usd: Decimal
    saha_commission_usd: Decimal | None
    legal_fee_usd: Decimal | None
    escrow_fee_usd: Decimal | None
    deal_summary: dict | None
    # NOTE: contract_storage_key is deliberately NOT exposed. It leaked the
    # internal object-store layout to both parties while serving no client
    # purpose — the contract is fetched through /contract, never by key
    # (security/AUDIT.md SAHA-021).
    contract_sha256: str | None = None
    law_firm: LawFirmResponse | None
    disbursements: list[DisbursementResponse] = []
    escrow_funded_at: datetime | None
    disbursed_at: datetime | None
    created_at: datetime
    updated_at: datetime
    model_config = {"from_attributes": True}


class AssignLawFirmRequest(BaseModel):
    law_firm_id: uuid.UUID


class ContractDraftResponse(BaseModel):
    contract_text: str
    transaction: TransactionResponse


class SignatureRow(BaseModel):
    signer_id: str
    signed_at: str


class SignatureStatusResponse(BaseModel):
    """Who has executed the contract, and against which bytes."""

    contract_sha256: str | None
    buyer_signed: bool
    seller_signed: bool
    fully_executed: bool
    signatures: list[SignatureRow] = []


class DisburseRequest(BaseModel):
    reason: str | None = Field(default=None, max_length=500)
