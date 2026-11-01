import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas.admin import (
    AdminListingRow,
    AdminProposalRow,
    AdminReviewRow,
    AdminTransactionRow,
    AdminUserDetail,
    AdminUserRow,
    AuditLogRow,
    CreateLawFirmRequest,
    DisbursementRow,
    LawFirmRow,
    PlatformStats,
    ResolveDisputeRequest,
    SetActiveRequest,
    SetKYCRequest,
    SetRoleRequest,
    UpdateLawFirmRequest,
)
from app.api.schemas.demand import DemandOverviewResponse
from app.api.schemas.open_resource import (
    OpenResourceCreate,
    OpenResourceResponse,
    OpenResourceUpdate,
    RejectResourceRequest,
)
from app.core.audit import write_audit_log
from app.core.security import require_admin
from app.db.models.listing import ListingStatus
from app.db.models.open_resource import OpenResourceStatus, OpenResourceType
from app.db.models.transaction import TransactionStatus
from app.db.models.user import KYCStatus, User, UserRole
from app.db.session import get_db
from app.services import admin as admin_svc
from app.services import demand as demand_svc
from app.services import notifications as notif_svc
from app.services import open_resources as resource_svc

router = APIRouter(prefix="/api/v1/admin", tags=["admin"])


def _audit(background_tasks: BackgroundTasks, admin: User, action: str, resource_type: str,
           resource_id: uuid.UUID | None, metadata: dict | None = None) -> None:
    background_tasks.add_task(
        write_audit_log, action=action, user_id=admin.id,
        resource_type=resource_type, resource_id=resource_id, metadata=metadata or {},
    )


# ── Overview ─────────────────────────────────────────────────────────────────

@router.get("/stats", response_model=PlatformStats)
async def platform_stats(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    return await admin_svc.get_platform_stats(db)


@router.get("/demand", response_model=DemandOverviewResponse)
async def demand_overview(
    days: int = Query(default=30, ge=1, le=365),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    return await demand_svc.get_demand_overview(db, days=days)


# ── Users ────────────────────────────────────────────────────────────────────

@router.get("/users", response_model=list[AdminUserRow])
async def list_users(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    search: str | None = Query(default=None, max_length=255),
    role: UserRole | None = None,
    kyc_status: KYCStatus | None = None,
    is_active: bool | None = None,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    return await admin_svc.list_users(db, limit, offset, search, role, kyc_status, is_active)


@router.get("/users/{user_id}", response_model=AdminUserDetail)
async def get_user_detail(
    user_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    detail = await admin_svc.get_user_detail(db, user_id)
    if detail is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return detail


@router.post("/users/{user_id}/active", response_model=AdminUserRow)
async def set_user_active(
    user_id: uuid.UUID,
    body: SetActiveRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
):
    user = await admin_svc.set_user_active(db, user_id, body.is_active, admin.id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    _audit(background_tasks, admin, "admin.user_active_set", "user", user_id,
           {"is_active": body.is_active})
    return user


@router.post("/users/{user_id}/role", response_model=AdminUserRow)
async def set_user_role(
    user_id: uuid.UUID,
    body: SetRoleRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
):
    user = await admin_svc.set_user_role(db, user_id, body.role, admin.id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    _audit(background_tasks, admin, "admin.user_role_changed", "user", user_id,
           {"new_role": body.role.value})
    return user


@router.post("/users/{user_id}/kyc", response_model=AdminUserRow)
async def set_user_kyc(
    user_id: uuid.UUID,
    body: SetKYCRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
):
    user = await admin_svc.set_user_kyc(db, user_id, body.kyc_status)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    _audit(background_tasks, admin, "admin.user_kyc_override", "user", user_id,
           {"new_status": body.kyc_status.value, "reason": body.reason})
    return user


# ── Listings (moderation) ────────────────────────────────────────────────────

async def _listing_row(db: AsyncSession, listing) -> dict:
    creator = await db.get(User, listing.creator_id)
    return {
        "id": listing.id, "title": listing.title, "status": listing.status.value,
        "product_category": listing.product_category, "view_count": listing.view_count,
        "creator_id": listing.creator_id,
        "creator_email": creator.email if creator else "",
        "created_at": listing.created_at, "updated_at": listing.updated_at,
    }


@router.get("/listings", response_model=list[AdminListingRow])
async def list_listings(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    status_filter: ListingStatus | None = Query(default=None, alias="status"),
    search: str | None = Query(default=None, max_length=255),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    return await admin_svc.list_listings(db, limit, offset, status_filter, search)


@router.post("/listings/{listing_id}/archive", response_model=AdminListingRow)
async def archive_listing(
    listing_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
):
    listing = await admin_svc.archive_listing(db, listing_id)
    if listing is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Listing not found")
    _audit(background_tasks, admin, "admin.listing_archived", "listing", listing_id,
           {"title": listing.title})
    return await _listing_row(db, listing)


@router.post("/listings/{listing_id}/restore", response_model=AdminListingRow)
async def restore_listing(
    listing_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
):
    listing = await admin_svc.restore_listing(db, listing_id)
    if listing is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Listing not found")
    _audit(background_tasks, admin, "admin.listing_restored", "listing", listing_id,
           {"title": listing.title})
    return await _listing_row(db, listing)


# ── Proposals ────────────────────────────────────────────────────────────────

@router.get("/proposals", response_model=list[AdminProposalRow])
async def list_proposals(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    status_filter: str | None = Query(default=None, alias="status"),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    return await admin_svc.list_proposals(db, limit, offset, status_filter)


# ── Transactions ─────────────────────────────────────────────────────────────

@router.get("/transactions", response_model=list[AdminTransactionRow])
async def list_transactions(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    status_filter: TransactionStatus | None = Query(default=None, alias="status"),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    return await admin_svc.list_transactions(db, limit, offset, status_filter)


@router.post("/transactions/{transaction_id}/dispute", response_model=AdminTransactionRow)
async def dispute_transaction(
    transaction_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
):
    txn = await admin_svc.dispute_transaction(db, transaction_id)
    if txn is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Transaction not found")
    _audit(background_tasks, admin, "admin.transaction_disputed", "transaction", transaction_id)
    return txn


@router.post("/transactions/{transaction_id}/resolve", response_model=AdminTransactionRow)
async def resolve_dispute(
    transaction_id: uuid.UUID,
    body: ResolveDisputeRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
):
    txn = await admin_svc.resolve_dispute(db, transaction_id, body.resolution)
    if txn is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Transaction not found")
    _audit(background_tasks, admin, "admin.dispute_resolved", "transaction", transaction_id,
           {"resolution": body.resolution, "reason": body.reason})
    return txn


# ── Reviews (moderation) ─────────────────────────────────────────────────────

@router.get("/reviews", response_model=list[AdminReviewRow])
async def list_reviews(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    return await admin_svc.list_reviews(db, limit, offset)


@router.delete("/reviews/{review_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_review(
    review_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
):
    deleted = await admin_svc.delete_review(db, review_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Review not found")
    _audit(background_tasks, admin, "admin.review_deleted", "review", review_id)


# ── Law firm partners ────────────────────────────────────────────────────────

@router.get("/law-firms", response_model=list[LawFirmRow])
async def list_law_firms(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    return await admin_svc.list_law_firms(db)


@router.post("/law-firms", response_model=LawFirmRow, status_code=status.HTTP_201_CREATED)
async def create_law_firm(
    body: CreateLawFirmRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
):
    firm = await admin_svc.create_law_firm(db, body.name, body.jurisdictions, body.contact_email)
    _audit(background_tasks, admin, "admin.law_firm_created", "law_firm", firm.id, {"name": firm.name})
    return firm


@router.patch("/law-firms/{firm_id}", response_model=LawFirmRow)
async def update_law_firm(
    firm_id: uuid.UUID,
    body: UpdateLawFirmRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
):
    firm = await admin_svc.update_law_firm(
        db, firm_id, body.name, body.jurisdictions, body.contact_email, body.is_active
    )
    if firm is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Law firm not found")
    _audit(background_tasks, admin, "admin.law_firm_updated", "law_firm", firm_id,
           body.model_dump(exclude_none=True))
    return firm


# ── Open Innovation Library (curation) ───────────────────────────────────────

@router.get("/open-resources", response_model=list[OpenResourceResponse])
async def list_open_resources(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    q: str | None = Query(default=None, max_length=255),
    resource_type: OpenResourceType | None = None,
    status_filter: OpenResourceStatus | None = Query(default=None, alias="status"),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    # Admin view includes archived (is_active=false) and pending/rejected entries.
    return await resource_svc.browse(
        db, q=q, resource_type=resource_type, limit=limit, offset=offset,
        include_inactive=True, status=status_filter,
    )


@router.post("/open-resources", response_model=OpenResourceResponse, status_code=status.HTTP_201_CREATED)
async def create_open_resource(
    body: OpenResourceCreate,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
):
    resource = await resource_svc.create_resource(db, body, admin.id)
    _audit(background_tasks, admin, "admin.open_resource_created", "open_resource", resource.id,
           {"title": resource.title, "type": resource.resource_type.value})
    return resource


@router.patch("/open-resources/{resource_id}", response_model=OpenResourceResponse)
async def update_open_resource(
    resource_id: uuid.UUID,
    body: OpenResourceUpdate,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
):
    resource = await resource_svc.update_resource(db, resource_id, body)
    if resource is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Resource not found")
    _audit(background_tasks, admin, "admin.open_resource_updated", "open_resource", resource_id,
           body.model_dump(exclude_unset=True, mode="json"))
    return resource


@router.post("/open-resources/{resource_id}/approve", response_model=OpenResourceResponse)
async def approve_open_resource(
    resource_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
):
    resource = await resource_svc.moderate_resource(db, resource_id, approve=True)
    if resource is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Resource not found")
    _audit(background_tasks, admin, "admin.open_resource_approved", "open_resource", resource_id,
           {"title": resource.title})
    background_tasks.add_task(
        notif_svc.notify, resource.added_by,
        "library.submission_approved", "Library submission approved",
        f"“{resource.title}” is now live in the Open Innovation Library. Thanks for contributing!",
        "/dashboard/library",
    )
    return resource


@router.post("/open-resources/{resource_id}/reject", response_model=OpenResourceResponse)
async def reject_open_resource(
    resource_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    body: RejectResourceRequest | None = None,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
):
    resource = await resource_svc.moderate_resource(db, resource_id, approve=False)
    if resource is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Resource not found")
    reason = body.reason if body and body.reason else None
    _audit(background_tasks, admin, "admin.open_resource_rejected", "open_resource", resource_id,
           {"title": resource.title, "reason": reason})
    background_tasks.add_task(
        notif_svc.notify, resource.added_by,
        "library.submission_rejected", "Library submission declined",
        f"“{resource.title}” wasn't accepted into the library."
        + (f" Reason: {reason}" if reason else " Check the license and source, then feel free to resubmit."),
        "/dashboard/library",
    )
    return resource


# ── Revenue ledger ───────────────────────────────────────────────────────────

@router.get("/disbursements", response_model=list[DisbursementRow])
async def list_disbursements(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    return await admin_svc.list_disbursements(db, limit, offset)


# ── Audit logs ───────────────────────────────────────────────────────────────

@router.get("/audit-logs", response_model=list[AuditLogRow])
async def list_audit_logs(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    action: str | None = Query(default=None, max_length=100),
    user_id: uuid.UUID | None = None,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    return await admin_svc.list_audit_logs(db, limit, offset, action, user_id)
