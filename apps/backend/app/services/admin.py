"""
Admin service: platform oversight and management over existing tables
(users, listings, proposals, transactions, disbursements, reviews, law firms,
audit_logs). No admin-specific tables — gated by role == admin at the API layer.
"""

import uuid

import structlog
from fastapi import HTTPException, status
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.audit_log import AuditLog
from app.db.models.listing import IPListing, ListingStatus
from app.db.models.proposal import Proposal
from app.db.models.review import Review
from app.db.models.transaction import Disbursement, LawFirmPartner, Transaction, TransactionStatus
from app.db.models.user import KYCStatus, User, UserRole

logger = structlog.get_logger()


async def _count_by(db: AsyncSession, column) -> dict[str, int]:
    rows = (await db.execute(select(column, func.count()).group_by(column))).all()
    return {str(k.value if hasattr(k, "value") else k): int(n) for k, n in rows}


async def get_platform_stats(db: AsyncSession) -> dict:
    users_total = (await db.execute(select(func.count()).select_from(User))).scalar() or 0
    listings_total = (await db.execute(select(func.count()).select_from(IPListing))).scalar() or 0
    proposals_total = (await db.execute(select(func.count()).select_from(Proposal))).scalar() or 0
    transactions_total = (await db.execute(select(func.count()).select_from(Transaction))).scalar() or 0
    reviews_total = (await db.execute(select(func.count()).select_from(Review))).scalar() or 0

    disbursed = (await db.execute(select(func.coalesce(func.sum(Disbursement.ip_holder_amount_usd), 0)))).scalar()
    commission = (await db.execute(select(func.coalesce(func.sum(Disbursement.saha_commission_usd), 0)))).scalar()
    pipeline = (await db.execute(
        select(func.coalesce(func.sum(Transaction.deal_value_usd), 0)).where(
            Transaction.status.notin_([TransactionStatus.COMPLETED, TransactionStatus.CANCELLED])
        )
    )).scalar()

    return {
        "users_total": users_total,
        "users_by_role": await _count_by(db, User.role),
        "listings_total": listings_total,
        "listings_by_status": await _count_by(db, IPListing.status),
        "proposals_total": proposals_total,
        "proposals_by_status": await _count_by(db, Proposal.status),
        "transactions_total": transactions_total,
        "transactions_by_status": await _count_by(db, Transaction.status),
        "reviews_total": reviews_total,
        "total_disbursed_usd": float(disbursed or 0),
        "total_commission_usd": float(commission or 0),
        "pipeline_value_usd": float(pipeline or 0),
    }


# ── Users ────────────────────────────────────────────────────────────────────

async def list_users(
    db: AsyncSession,
    limit: int,
    offset: int,
    search: str | None = None,
    role: UserRole | None = None,
    kyc_status: KYCStatus | None = None,
    is_active: bool | None = None,
) -> list[User]:
    q = select(User)
    if search:
        like = f"%{search.strip()}%"
        q = q.where(or_(User.email.ilike(like), User.full_name.ilike(like)))
    if role is not None:
        q = q.where(User.role == role)
    if kyc_status is not None:
        q = q.where(User.kyc_status == kyc_status)
    if is_active is not None:
        q = q.where(User.is_active == is_active)
    result = await db.execute(q.order_by(User.created_at.desc()).limit(limit).offset(offset))
    return list(result.scalars().all())


async def get_user_detail(db: AsyncSession, user_id: uuid.UUID) -> dict | None:
    user = await db.get(User, user_id)
    if user is None:
        return None

    listings = (await db.execute(
        select(func.count()).select_from(IPListing).where(IPListing.creator_id == user_id)
    )).scalar() or 0
    proposals = (await db.execute(
        select(func.count()).select_from(Proposal).where(
            or_(Proposal.buyer_id == user_id, Proposal.seller_id == user_id)
        )
    )).scalar() or 0
    transactions = (await db.execute(
        select(func.count()).select_from(Transaction).where(
            or_(Transaction.buyer_id == user_id, Transaction.seller_id == user_id)
        )
    )).scalar() or 0
    avg_rating, review_count = (await db.execute(
        select(func.avg(Review.rating), func.count(Review.id)).where(Review.reviewee_id == user_id)
    )).one()
    recent_audit = (await db.execute(
        select(AuditLog).where(AuditLog.user_id == user_id)
        .order_by(AuditLog.created_at.desc()).limit(20)
    )).scalars().all()

    return {
        "user": user,
        "listings_count": int(listings),
        "proposals_count": int(proposals),
        "transactions_count": int(transactions),
        "average_rating": round(float(avg_rating), 2) if avg_rating is not None else None,
        "review_count": int(review_count),
        "recent_audit": list(recent_audit),
    }


async def set_user_active(
    db: AsyncSession, user_id: uuid.UUID, is_active: bool, acting_admin_id: uuid.UUID
) -> User | None:
    if user_id == acting_admin_id and not is_active:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="You cannot deactivate your own account")
    user = await db.get(User, user_id)
    if user is None:
        return None
    if not is_active:
        from app.services.chat import revoke_user
        await revoke_user(db, user_id)
    user.is_active = is_active
    await db.commit()
    await db.refresh(user)
    return user


async def set_user_role(
    db: AsyncSession, user_id: uuid.UUID, role: UserRole, acting_admin_id: uuid.UUID
) -> User | None:
    if user_id == acting_admin_id and role != UserRole.ADMIN:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="You cannot remove your own admin role")
    user = await db.get(User, user_id)
    if user is None:
        return None
    user.role = role
    await db.commit()
    await db.refresh(user)
    return user


async def set_user_kyc(db: AsyncSession, user_id: uuid.UUID, kyc_status: KYCStatus) -> User | None:
    """Manual KYC override — for support cases where the provider flow stalls.
    Every use is audited at the API layer."""
    user = await db.get(User, user_id)
    if user is None:
        return None
    user.kyc_status = kyc_status
    await db.commit()
    await db.refresh(user)
    return user


# ── Listings (moderation) ────────────────────────────────────────────────────

async def list_listings(
    db: AsyncSession,
    limit: int,
    offset: int,
    status_filter: ListingStatus | None = None,
    search: str | None = None,
) -> list[dict]:
    q = select(IPListing, User.email).join(User, User.id == IPListing.creator_id)
    if status_filter is not None:
        q = q.where(IPListing.status == status_filter)
    if search:
        q = q.where(IPListing.title.ilike(f"%{search.strip()}%"))
    rows = (await db.execute(q.order_by(IPListing.created_at.desc()).limit(limit).offset(offset))).all()
    return [
        {
            "id": l.id, "title": l.title, "status": l.status.value,
            "product_category": l.product_category, "view_count": l.view_count,
            "creator_id": l.creator_id, "creator_email": email,
            "created_at": l.created_at, "updated_at": l.updated_at,
        }
        for l, email in rows
    ]


async def archive_listing(db: AsyncSession, listing_id: uuid.UUID) -> IPListing | None:
    """Moderation takedown: removes from the marketplace and the vector index."""
    listing = await db.get(IPListing, listing_id)
    if listing is None:
        return None
    if listing.qdrant_point_id:
        try:
            from app.services.embeddings import remove_listing
            await remove_listing(listing.qdrant_point_id)
        except Exception as e:
            logger.warning("qdrant_deindex_failed", listing_id=str(listing_id), error=str(e))
    listing.status = ListingStatus.ARCHIVED
    listing.qdrant_point_id = None
    await db.commit()
    await db.refresh(listing)
    return listing


async def restore_listing(db: AsyncSession, listing_id: uuid.UUID) -> IPListing | None:
    """Returns an archived listing to 'review' so the creator can re-publish."""
    listing = await db.get(IPListing, listing_id)
    if listing is None:
        return None
    if listing.status != ListingStatus.ARCHIVED:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Only archived listings can be restored")
    listing.status = ListingStatus.REVIEW
    await db.commit()
    await db.refresh(listing)
    return listing


# ── Proposals ────────────────────────────────────────────────────────────────

async def list_proposals(
    db: AsyncSession, limit: int, offset: int, status_filter: str | None = None
) -> list[dict]:
    q = select(Proposal, IPListing.title).join(IPListing, IPListing.id == Proposal.listing_id)
    if status_filter:
        q = q.where(Proposal.status == status_filter)
    rows = (await db.execute(q.order_by(Proposal.updated_at.desc()).limit(limit).offset(offset))).all()
    return [
        {
            "id": p.id, "listing_id": p.listing_id, "listing_title": title,
            "buyer_id": p.buyer_id, "seller_id": p.seller_id,
            "status": p.status.value,
            "offer_amount_usd": float(p.offer_amount_usd) if p.offer_amount_usd is not None else None,
            "version": p.version, "created_at": p.created_at, "updated_at": p.updated_at,
        }
        for p, title in rows
    ]


# ── Transactions ─────────────────────────────────────────────────────────────

async def list_transactions(
    db: AsyncSession, limit: int, offset: int, status_filter: TransactionStatus | None = None
) -> list[Transaction]:
    q = select(Transaction)
    if status_filter is not None:
        q = q.where(Transaction.status == status_filter)
    result = await db.execute(q.order_by(Transaction.updated_at.desc()).limit(limit).offset(offset))
    return list(result.scalars().all())


# Dispute can be opened from any in-flight status; terminal states are immutable.
_DISPUTABLE = set(TransactionStatus) - {
    TransactionStatus.COMPLETED, TransactionStatus.CANCELLED, TransactionStatus.DISPUTED
}


async def dispute_transaction(db: AsyncSession, transaction_id: uuid.UUID) -> Transaction | None:
    txn = await db.get(Transaction, transaction_id)
    if txn is None:
        return None
    if txn.status not in _DISPUTABLE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot open a dispute on a {txn.status.value} transaction",
        )
    txn.status = TransactionStatus.DISPUTED
    await db.commit()
    from app.services.transactions import get_transaction
    return await get_transaction(db, transaction_id)


async def resolve_dispute(
    db: AsyncSession, transaction_id: uuid.UUID, resolution: str
) -> Transaction | None:
    """resolution: 'complete' | 'cancel'. Note: an admin resolution only settles the
    record — any refund/disbursement is handled out-of-band via Stripe."""
    txn = await db.get(Transaction, transaction_id)
    if txn is None:
        return None
    if txn.status != TransactionStatus.DISPUTED:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Transaction is not disputed")
    if resolution == "complete":
        txn.status = TransactionStatus.COMPLETED
    elif resolution == "cancel":
        txn.status = TransactionStatus.CANCELLED
    else:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="resolution must be 'complete' or 'cancel'")
    await db.commit()
    from app.services.transactions import get_transaction
    return await get_transaction(db, transaction_id)


# ── Reviews (moderation) ─────────────────────────────────────────────────────

async def list_reviews(db: AsyncSession, limit: int, offset: int) -> list[Review]:
    result = await db.execute(
        select(Review).order_by(Review.created_at.desc()).limit(limit).offset(offset)
    )
    return list(result.scalars().all())


async def delete_review(db: AsyncSession, review_id: uuid.UUID) -> bool:
    review = await db.get(Review, review_id)
    if review is None:
        return False
    await db.delete(review)
    await db.commit()
    return True


# ── Law firm partners ────────────────────────────────────────────────────────

async def list_law_firms(db: AsyncSession) -> list[LawFirmPartner]:
    result = await db.execute(select(LawFirmPartner).order_by(LawFirmPartner.name))
    return list(result.scalars().all())


async def create_law_firm(
    db: AsyncSession, name: str, jurisdictions: list[str], contact_email: str | None
) -> LawFirmPartner:
    firm = LawFirmPartner(name=name, jurisdictions=jurisdictions, contact_email=contact_email)
    db.add(firm)
    await db.commit()
    await db.refresh(firm)
    return firm


async def update_law_firm(
    db: AsyncSession,
    firm_id: uuid.UUID,
    name: str | None = None,
    jurisdictions: list[str] | None = None,
    contact_email: str | None = None,
    is_active: bool | None = None,
) -> LawFirmPartner | None:
    firm = await db.get(LawFirmPartner, firm_id)
    if firm is None:
        return None
    if name is not None:
        firm.name = name
    if jurisdictions is not None:
        firm.jurisdictions = jurisdictions
    if contact_email is not None:
        firm.contact_email = contact_email
    if is_active is not None:
        firm.is_active = is_active
    await db.commit()
    await db.refresh(firm)
    return firm


# ── Revenue ledger ───────────────────────────────────────────────────────────

async def list_disbursements(db: AsyncSession, limit: int, offset: int) -> list[Disbursement]:
    result = await db.execute(
        select(Disbursement).order_by(Disbursement.created_at.desc()).limit(limit).offset(offset)
    )
    return list(result.scalars().all())


# ── Audit logs ───────────────────────────────────────────────────────────────

async def list_audit_logs(
    db: AsyncSession,
    limit: int,
    offset: int,
    action: str | None = None,
    user_id: uuid.UUID | None = None,
) -> list[AuditLog]:
    q = select(AuditLog)
    if action:
        q = q.where(AuditLog.action.ilike(f"{action.strip()}%"))
    if user_id is not None:
        q = q.where(AuditLog.user_id == user_id)
    result = await db.execute(q.order_by(AuditLog.created_at.desc()).limit(limit).offset(offset))
    return list(result.scalars().all())
