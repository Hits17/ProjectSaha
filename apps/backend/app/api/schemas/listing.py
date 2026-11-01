import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field


class CreateListingRequest(BaseModel):
    title: str = Field(..., min_length=3, max_length=500)
    product_category: str | None = None
    description: str | None = None


class DialogueMessageRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=4000)


class PublishListingRequest(BaseModel):
    public_description: str | None = None


class BOMItemResponse(BaseModel):
    id: uuid.UUID
    material_name: str
    specification: str | None
    quantity_per_unit: Decimal
    unit_of_measure: str
    shelf_life_days: int | None
    procurement_cadence: str | None
    is_critical: bool
    notes: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class VaultAssetResponse(BaseModel):
    id: uuid.UUID
    original_filename: str
    file_size_bytes: int
    content_type: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


# ── Tiered disclosure ────────────────────────────────────────────────────────
# Listing content is split by audience at the RESPONSE MODEL, not by filtering
# inside one model. Conditional filtering is how confidential fields leak: add a
# field, forget the branch, and it ships. Two classes means the tier of every
# field is decided once, at declaration.
#
# T0 (PublicListingResponse) is world-readable — it is returned to anonymous
# callers on /listings/public, /listings/{id} and search results.
# T2 (OwnerListingResponse) is the creator's private view.
#
# See security/AUDIT.md SAHA-003 and security/ROADMAP.md §2.1.


class PublicListingResponse(BaseModel):
    """Teaser tier (T0). WORLD-READABLE.

    Anything added to this class becomes visible to unauthenticated callers —
    that is the entire contract of this model. Never add `description`,
    `bom_items`, `vault_assets`, `equipment_requirements` or
    `batch_size_definition`: those are the manufacturing recipe and the
    confidential document inventory.
    """

    id: uuid.UUID
    creator_id: uuid.UUID
    title: str
    product_category: str | None
    tags: list[str]
    public_description: str | None
    status: str
    created_at: datetime

    model_config = {"from_attributes": True}


class OwnerListingResponse(PublicListingResponse):
    """Full tier (T2). Returned ONLY to the listing's creator.

    Carries the trade-secret-grade fields: the private description, the bill of
    materials, and the vault asset inventory.
    """

    description: str | None
    equipment_requirements: list[str]
    batch_size_definition: str | None
    view_count: int
    bom_items: list[BOMItemResponse] = []
    vault_assets: list[VaultAssetResponse] = []
    updated_at: datetime

    model_config = {"from_attributes": True}


# Backwards-compatible alias for owner-facing call sites.
ListingResponse = OwnerListingResponse


class DialogueResponse(BaseModel):
    reply: str
    messages: list[dict]


class FinalizeBOMResponse(BaseModel):
    bom_items: list[BOMItemResponse]
    listing: ListingResponse
