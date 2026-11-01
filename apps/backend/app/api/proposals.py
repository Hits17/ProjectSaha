import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas.proposal import (
    CounterOfferRequest,
    CreateProposalRequest,
    MessageResponse,
    ProposalResponse,
    SendMessageRequest,
    SubmitProposalRequest,
)
from app.core.audit import write_audit_log
from app.core.security import require_verified_user
from app.db.models.user import User
from app.db.session import get_db
from app.services import messages as msg_svc
from app.services import notifications as notif_svc
from app.services import proposals as proposal_svc

router = APIRouter(prefix="/api/v1/proposals", tags=["negotiation"])


def _check_access(proposal, user_id: uuid.UUID):
    if proposal.buyer_id != user_id and proposal.seller_id != user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not a participant")


def _counterparty(proposal, user_id: uuid.UUID) -> uuid.UUID:
    """The participant who is NOT the actor — the one to notify."""
    return proposal.seller_id if user_id == proposal.buyer_id else proposal.buyer_id


@router.post("", response_model=ProposalResponse, status_code=status.HTTP_201_CREATED)
async def create_proposal(
    body: CreateProposalRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_verified_user),
):
    proposal = await proposal_svc.create_proposal(db, body.listing_id, current_user.id)
    background_tasks.add_task(
        write_audit_log, action="proposal.created", user_id=current_user.id,
        resource_type="proposal", resource_id=proposal.id,
        metadata={"listing_id": str(body.listing_id)},
    )
    return proposal


@router.get("", response_model=list[ProposalResponse])
async def list_proposals(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_verified_user),
):
    return await proposal_svc.get_proposals_for_user(db, current_user.id)


@router.get("/{proposal_id}", response_model=ProposalResponse)
async def get_proposal(
    proposal_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_verified_user),
):
    proposal = await proposal_svc.get_proposal(db, proposal_id)
    if not proposal:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Proposal not found")
    _check_access(proposal, current_user.id)
    return proposal


@router.post("/{proposal_id}/submit", response_model=ProposalResponse)
async def submit_proposal(
    proposal_id: uuid.UUID,
    body: SubmitProposalRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_verified_user),
):
    proposal = await proposal_svc.get_proposal(db, proposal_id)
    if not proposal:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Proposal not found")

    proposal = await proposal_svc.submit_proposal(
        db, proposal, current_user.id,
        body.offer_amount_usd, body.license_type, body.territory, body.duration_months, body.notes,
    )
    background_tasks.add_task(
        write_audit_log, action="proposal.submitted", user_id=current_user.id,
        resource_type="proposal", resource_id=proposal_id,
        metadata={"offer_usd": str(body.offer_amount_usd)},
    )
    background_tasks.add_task(
        notif_svc.notify, _counterparty(proposal, current_user.id),
        "proposal.submitted", "New offer received",
        f"An offer of ${body.offer_amount_usd:,.0f} was submitted on your listing.",
        f"/dashboard/proposals/{proposal_id}",
    )
    return proposal


@router.post("/{proposal_id}/counter", response_model=ProposalResponse)
async def counter_offer(
    proposal_id: uuid.UUID,
    body: CounterOfferRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_verified_user),
):
    proposal = await proposal_svc.get_proposal(db, proposal_id)
    if not proposal:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Proposal not found")

    proposal = await proposal_svc.counter_offer(
        db, proposal, current_user.id,
        body.offer_amount_usd, body.license_type, body.territory, body.duration_months, body.notes,
    )
    background_tasks.add_task(
        write_audit_log, action="proposal.counter_offered", user_id=current_user.id,
        resource_type="proposal", resource_id=proposal_id,
        metadata={"version": proposal.version},
    )
    background_tasks.add_task(
        notif_svc.notify, _counterparty(proposal, current_user.id),
        "proposal.counter_offered", "Counter-offer received",
        f"The other party countered with new terms (v{proposal.version}).",
        f"/dashboard/proposals/{proposal_id}",
    )
    return proposal


@router.post("/{proposal_id}/accept", response_model=ProposalResponse)
async def accept_proposal(
    proposal_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_verified_user),
):
    proposal = await proposal_svc.get_proposal(db, proposal_id)
    if not proposal:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Proposal not found")

    proposal = await proposal_svc.accept_proposal(db, proposal, current_user.id)
    background_tasks.add_task(
        write_audit_log, action="proposal.accepted", user_id=current_user.id,
        resource_type="proposal", resource_id=proposal_id, metadata={},
    )
    background_tasks.add_task(
        notif_svc.notify, _counterparty(proposal, current_user.id),
        "proposal.accepted", "Offer accepted 🎉",
        "Your proposal was accepted — a transaction has been created.",
        "/dashboard/transactions",
    )
    return proposal


@router.post("/{proposal_id}/reject", response_model=ProposalResponse)
async def reject_proposal(
    proposal_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_verified_user),
):
    proposal = await proposal_svc.get_proposal(db, proposal_id)
    if not proposal:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Proposal not found")

    proposal = await proposal_svc.reject_proposal(db, proposal, current_user.id)
    background_tasks.add_task(
        write_audit_log, action="proposal.rejected", user_id=current_user.id,
        resource_type="proposal", resource_id=proposal_id, metadata={},
    )
    return proposal


@router.post("/{proposal_id}/withdraw", response_model=ProposalResponse)
async def withdraw_proposal(
    proposal_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_verified_user),
):
    proposal = await proposal_svc.get_proposal(db, proposal_id)
    if not proposal:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Proposal not found")

    proposal = await proposal_svc.withdraw_proposal(db, proposal, current_user.id)
    background_tasks.add_task(
        write_audit_log, action="proposal.withdrawn", user_id=current_user.id,
        resource_type="proposal", resource_id=proposal_id, metadata={},
    )
    return proposal


@router.post("/{proposal_id}/messages", response_model=MessageResponse, status_code=status.HTTP_201_CREATED)
async def send_message(
    proposal_id: uuid.UUID,
    body: SendMessageRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_verified_user),
):
    proposal = await proposal_svc.get_proposal(db, proposal_id)
    if not proposal:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Proposal not found")

    msg = await msg_svc.send_message(db, proposal, current_user.id, body.content)
    background_tasks.add_task(
        notif_svc.notify, _counterparty(proposal, current_user.id),
        "proposal.message", "New negotiation message",
        "You have a new message on a proposal.",
        f"/dashboard/proposals/{proposal_id}",
    )
    return MessageResponse(**{k: v for k, v in msg.items()})


@router.get("/{proposal_id}/messages", response_model=list[MessageResponse])
async def list_messages(
    proposal_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_verified_user),
):
    proposal = await proposal_svc.get_proposal(db, proposal_id)
    if not proposal:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Proposal not found")

    msgs = await msg_svc.get_messages(db, proposal, current_user.id)
    return [MessageResponse(**m) for m in msgs]
