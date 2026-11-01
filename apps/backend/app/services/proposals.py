import uuid
from datetime import datetime, timezone
from decimal import Decimal

from fastapi import HTTPException, status
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models.listing import IPListing
from app.db.models.proposal import Proposal, ProposalStatus, ProposalVersion


async def get_proposal(db: AsyncSession, proposal_id: uuid.UUID) -> Proposal | None:
    result = await db.execute(
        select(Proposal)
        .options(selectinload(Proposal.versions), selectinload(Proposal.messages))
        .where(Proposal.id == proposal_id)
        .execution_options(populate_existing=True)
    )
    return result.scalar_one_or_none()


async def get_proposals_for_user(db: AsyncSession, user_id: uuid.UUID) -> list[Proposal]:
    result = await db.execute(
        select(Proposal)
        .options(selectinload(Proposal.versions))
        .where(or_(Proposal.buyer_id == user_id, Proposal.seller_id == user_id))
        .order_by(Proposal.updated_at.desc())
    )
    return list(result.scalars().all())


async def create_proposal(
    db: AsyncSession,
    listing_id: uuid.UUID,
    buyer_id: uuid.UUID,
) -> Proposal:
    listing = await db.get(IPListing, listing_id)
    if not listing:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Listing not found")

    if listing.status.value != "published":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Can only propose on published listings")

    if listing.creator_id == buyer_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot propose on your own listing")

    existing = await db.execute(
        select(Proposal)
        .where(Proposal.listing_id == listing_id)
        .where(Proposal.buyer_id == buyer_id)
        .where(Proposal.status.notin_(["rejected", "withdrawn"]))
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="You already have an active proposal on this listing")

    proposal = Proposal(
        listing_id=listing_id,
        buyer_id=buyer_id,
        seller_id=listing.creator_id,
        status=ProposalStatus.DRAFT,
    )
    db.add(proposal)
    await db.commit()

    from app.core import metrics
    metrics.proposals_created_total.inc()

    return await get_proposal(db, proposal.id)


async def submit_proposal(
    db: AsyncSession,
    proposal: Proposal,
    buyer_id: uuid.UUID,
    offer_amount_usd: Decimal,
    license_type: str,
    territory: str,
    duration_months: int,
    notes: str | None,
) -> Proposal:
    _require_buyer(proposal, buyer_id)
    if proposal.status != ProposalStatus.DRAFT:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Only draft proposals can be submitted")

    proposal.offer_amount_usd = offer_amount_usd
    proposal.license_type = license_type
    proposal.territory = territory
    proposal.duration_months = duration_months
    proposal.status = ProposalStatus.SUBMITTED
    proposal.version = 1

    version = ProposalVersion(
        proposal_id=proposal.id,
        version=1,
        offer_amount_usd=offer_amount_usd,
        license_type=license_type,
        territory=territory,
        duration_months=duration_months,
        proposed_by_id=buyer_id,
        notes=notes,
    )
    db.add(version)
    await db.commit()
    return await get_proposal(db, proposal.id)


async def counter_offer(
    db: AsyncSession,
    proposal: Proposal,
    proposer_id: uuid.UUID,
    offer_amount_usd: Decimal,
    license_type: str,
    territory: str,
    duration_months: int,
    notes: str | None,
) -> Proposal:
    _require_participant(proposal, proposer_id)
    if proposal.status not in (ProposalStatus.SUBMITTED, ProposalStatus.NDA_SIGNED, ProposalStatus.NEGOTIATING):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Cannot counter in status: {proposal.status.value}")

    proposal.offer_amount_usd = offer_amount_usd
    proposal.license_type = license_type
    proposal.territory = territory
    proposal.duration_months = duration_months
    proposal.status = ProposalStatus.NEGOTIATING
    proposal.version += 1

    version = ProposalVersion(
        proposal_id=proposal.id,
        version=proposal.version,
        offer_amount_usd=offer_amount_usd,
        license_type=license_type,
        territory=territory,
        duration_months=duration_months,
        proposed_by_id=proposer_id,
        notes=notes,
    )
    db.add(version)
    await db.commit()
    return await get_proposal(db, proposal.id)


async def accept_proposal(db: AsyncSession, proposal: Proposal, user_id: uuid.UUID) -> Proposal:
    _require_participant(proposal, user_id)
    if proposal.status not in (ProposalStatus.SUBMITTED, ProposalStatus.NEGOTIATING, ProposalStatus.NDA_SIGNED):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Cannot accept in status: {proposal.status.value}")

    # Only the counterparty of the latest offer can accept it — otherwise a party
    # could submit terms and immediately self-accept, creating a transaction the
    # other side never agreed to.
    latest = max(proposal.versions, key=lambda v: v.version, default=None)
    if latest is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No offer to accept")
    if latest.proposed_by_id == user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="The party who made the latest offer cannot accept it",
        )

    proposal.status = ProposalStatus.ACCEPTED
    await db.commit()

    # Auto-create transaction from accepted proposal
    try:
        from app.services.transactions import create_from_proposal
        await create_from_proposal(db, proposal)
    except Exception as e:
        import structlog
        structlog.get_logger().warning("transaction_auto_create_failed", error=str(e), proposal_id=str(proposal.id))

    return await get_proposal(db, proposal.id)


async def reject_proposal(db: AsyncSession, proposal: Proposal, user_id: uuid.UUID) -> Proposal:
    _require_participant(proposal, user_id)
    if proposal.status in (ProposalStatus.ACCEPTED, ProposalStatus.WITHDRAWN):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Cannot reject in status: {proposal.status.value}")

    proposal.status = ProposalStatus.REJECTED
    await db.commit()
    return await get_proposal(db, proposal.id)


async def withdraw_proposal(db: AsyncSession, proposal: Proposal, buyer_id: uuid.UUID) -> Proposal:
    _require_buyer(proposal, buyer_id)
    if proposal.status in (ProposalStatus.ACCEPTED, ProposalStatus.REJECTED, ProposalStatus.WITHDRAWN):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Cannot withdraw in status: {proposal.status.value}")

    proposal.status = ProposalStatus.WITHDRAWN
    await db.commit()
    return await get_proposal(db, proposal.id)


def _require_participant(proposal: Proposal, user_id: uuid.UUID) -> None:
    if proposal.buyer_id != user_id and proposal.seller_id != user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not a participant in this proposal")


def _require_buyer(proposal: Proposal, user_id: uuid.UUID) -> None:
    if proposal.buyer_id != user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only the buyer can perform this action")
