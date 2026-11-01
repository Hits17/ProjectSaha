import uuid

import structlog
from fastapi import (
    APIRouter, BackgroundTasks, Depends, File, HTTPException, Query, Request,
    UploadFile, status,
)
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai import sessions as ai_sessions
from app.core.ratelimit import ANON_READ_LIMIT, EXPENSIVE_LIMIT, limiter
from app.api.schemas.listing import (
    BOMItemResponse,
    CreateListingRequest,
    DialogueMessageRequest,
    DialogueResponse,
    FinalizeBOMResponse,
    ListingResponse,
    OwnerListingResponse,
    PublicListingResponse,
    PublishListingRequest,
    VaultAssetResponse,
)
from app.core.audit import write_audit_log
from app.core.security import get_optional_user, require_verified_user
from app.db.models.listing import IPVaultAsset, ListingStatus
from app.db.models.user import User
from app.db.session import get_db
from app.services import listings as listing_svc
from app.services import uploads as upload_svc
from app.services import vault as vault_svc

router = APIRouter(prefix="/api/v1/listings", tags=["listings"])
logger = structlog.get_logger()

MAX_FILE_MB = 50
MAX_FILE_BYTES = MAX_FILE_MB * 1024 * 1024

# Deep pagination is how a corpus gets walked end-to-end. Discovery is served by
# /api/v1/search; browsing is not meant to enumerate everything.
MAX_PUBLIC_OFFSET = 10_000


# Open-roles model (2026-06-10): any verified marketplace user may create and
# manage listings — authorization is ownership-based (_require_owner), not
# role-based. The signup role is a label, not a capability boundary.
def _require_owner(listing, user: User):
    if listing.creator_id != user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not your listing")


# ── Listing-owner endpoints ──────────────────────────────────────────────────

@router.post("", response_model=ListingResponse, status_code=status.HTTP_201_CREATED)
async def create_listing(
    body: CreateListingRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_verified_user),
):
    created = await listing_svc.create_listing(
        db, current_user.id, body.title, body.product_category, body.description
    )
    listing = await listing_svc.get_listing(db, created.id)
    background_tasks.add_task(
        write_audit_log,
        action="listing.created",
        user_id=current_user.id,
        resource_type="listing",
        resource_id=listing.id,
        metadata={"title": listing.title},
    )
    return listing


@router.get("/me", response_model=list[ListingResponse])
async def my_listings(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_verified_user),
):
    return await listing_svc.get_creator_listings(db, current_user.id)


@router.get("/public", response_model=list[PublicListingResponse])
@limiter.limit(ANON_READ_LIMIT)
async def public_listings(
    request: Request,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0, le=MAX_PUBLIC_OFFSET),
    db: AsyncSession = Depends(get_db),
):
    """Teaser tier only — see PublicListingResponse. `offset` is bounded so the
    corpus cannot be walked end-to-end in one pass."""
    return await listing_svc.get_public_listings(db, limit=limit, offset=offset)


@router.get("/{listing_id}", response_model=PublicListingResponse | OwnerListingResponse)
@limiter.limit(ANON_READ_LIMIT)
async def get_listing(
    listing_id: uuid.UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User | None = Depends(get_optional_user),
):
    listing = await listing_svc.get_listing(db, listing_id)
    if not listing:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Listing not found")

    is_owner = current_user is not None and listing.creator_id == current_user.id
    if not is_owner and listing.status != ListingStatus.PUBLISHED:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Listing not found")

    if listing.status == ListingStatus.PUBLISHED and not is_owner:
        await listing_svc.record_view(db, listing_id, current_user.id if current_user else None)
        listing = await listing_svc.get_listing(db, listing_id)

    # Tier the response on ownership. Non-owners — including authenticated
    # buyers — get the teaser only; confidential content is released through
    # the deal flow (see settlement.vault-access), never through browsing.
    if is_owner:
        return OwnerListingResponse.model_validate(listing)
    return PublicListingResponse.model_validate(listing)


@router.post("/{listing_id}/dialogue/start", response_model=DialogueResponse)
@limiter.limit(EXPENSIVE_LIMIT)
async def start_dialogue(
    listing_id: uuid.UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_verified_user),
):
    """Get the AI greeting for this listing (creates session if first time)."""
    listing = await listing_svc.get_listing(db, listing_id)
    if not listing:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Listing not found")
    _require_owner(listing, current_user)

    greeting = await listing_svc.get_ai_greeting(db, listing, current_user.id)
    messages = await ai_sessions.get_messages(listing_id, current_user.id)
    return DialogueResponse(reply=greeting, messages=messages)


@router.post("/{listing_id}/dialogue", response_model=DialogueResponse)
@limiter.limit(EXPENSIVE_LIMIT)
async def send_dialogue_message(
    listing_id: uuid.UUID,
    body: DialogueMessageRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_verified_user),
):
    listing = await listing_svc.get_listing(db, listing_id)
    if not listing:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Listing not found")
    _require_owner(listing, current_user)

    if listing.status not in (ListingStatus.DRAFT, ListingStatus.AI_GENERATING):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Dialogue is only available for draft listings",
        )

    reply = await listing_svc.send_dialogue_message(db, listing, current_user.id, body.message)
    messages = await ai_sessions.get_messages(listing_id, current_user.id)
    return DialogueResponse(reply=reply, messages=messages)


@router.get("/{listing_id}/dialogue", response_model=list[dict])
async def get_dialogue(
    listing_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_verified_user),
):
    listing = await listing_svc.get_listing(db, listing_id)
    if not listing:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Listing not found")
    _require_owner(listing, current_user)
    return await ai_sessions.get_messages(listing_id, current_user.id)


@router.post("/{listing_id}/finalize-bom", response_model=FinalizeBOMResponse)
@limiter.limit(EXPENSIVE_LIMIT)
async def finalize_bom(
    listing_id: uuid.UUID,
    request: Request,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_verified_user),
):
    listing = await listing_svc.get_listing(db, listing_id)
    if not listing:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Listing not found")
    _require_owner(listing, current_user)

    bom_items = await listing_svc.finalize_bom(db, listing, current_user.id)
    listing = await listing_svc.get_listing(db, listing_id)

    background_tasks.add_task(
        write_audit_log,
        action="listing.bom_finalized",
        user_id=current_user.id,
        resource_type="listing",
        resource_id=listing_id,
        metadata={"bom_item_count": len(bom_items)},
    )

    return FinalizeBOMResponse(
        bom_items=[BOMItemResponse.model_validate(i) for i in bom_items],
        listing=ListingResponse.model_validate(listing),
    )


@router.post("/{listing_id}/files", response_model=VaultAssetResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit(EXPENSIVE_LIMIT)
async def upload_vault_file(
    listing_id: uuid.UUID,
    request: Request,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_verified_user),
):
    listing = await listing_svc.get_listing(db, listing_id)
    if not listing:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Listing not found")
    _require_owner(listing, current_user)

    if listing.status == ListingStatus.PUBLISHED:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot upload files to a published listing")

    # Bounded streaming read + identification from the file's own bytes. The
    # client's declared Content-Type is not trusted: these files are handed to a
    # counterparty later, so what they actually are matters more than what the
    # uploader called them (security/AUDIT.md SAHA-018, SAHA-031).
    data, label, content_type = await upload_svc.validate_upload(file, MAX_FILE_BYTES)

    vault_meta = await vault_svc.store_encrypted_file(
        listing_id=listing_id,
        filename=file.filename or "upload",
        data=data,
        content_type=content_type,
    )

    asset = IPVaultAsset(
        listing_id=listing_id,
        storage_key=vault_meta["storage_key"],
        original_filename=upload_svc.safe_filename(file.filename),
        file_size_bytes=vault_meta["file_size_bytes"],
        content_type=content_type,
        encryption_key_id=vault_meta["encryption_key_id"],
        content_sha256=vault_meta["content_sha256"],
    )
    asset = await listing_svc.add_vault_asset(db, asset)

    background_tasks.add_task(
        write_audit_log,
        action="vault.file_uploaded",
        user_id=current_user.id,
        resource_type="listing",
        resource_id=listing_id,
        metadata={
            "asset_id": str(asset.id),
            "format": label,
            "declared_type": file.content_type,
            "resolved_type": content_type,
            "is_container": upload_svc.is_container(label),
            "size_bytes": vault_meta["file_size_bytes"],
            "sha256": vault_meta["content_sha256"],
        },
    )

    return asset


@router.post("/{listing_id}/publish", response_model=ListingResponse)
async def publish_listing(
    listing_id: uuid.UUID,
    body: PublishListingRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_verified_user),
):
    listing = await listing_svc.get_listing(db, listing_id)
    if not listing:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Listing not found")
    _require_owner(listing, current_user)

    listing = await listing_svc.publish_listing(db, listing, body.public_description)

    background_tasks.add_task(
        write_audit_log,
        action="listing.published",
        user_id=current_user.id,
        resource_type="listing",
        resource_id=listing_id,
        metadata={"title": listing.title},
    )

    return listing
