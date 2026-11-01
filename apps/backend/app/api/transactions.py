import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas.transaction import (
    AssignLawFirmRequest,
    ContractDraftResponse,
    LawFirmResponse,
    SignatureStatusResponse,
    TransactionResponse,
)
from app.core.audit import write_audit_log
from app.core.clientip import client_ip
from app.core.ratelimit import EXPENSIVE_LIMIT, limiter
from app.core.security import require_step_up, require_verified_user
from app.db.models.transaction import TransactionStatus
from app.db.models.user import User
from app.db.session import get_db
from app.services import transactions as txn_svc

router = APIRouter(prefix="/api/v1/transactions", tags=["legal"])


def _check_access(txn, user_id: uuid.UUID) -> None:
    if txn.buyer_id != user_id and txn.seller_id != user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not a party to this transaction")


@router.get("", response_model=list[TransactionResponse])
async def list_transactions(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_verified_user),
):
    return await txn_svc.get_transactions_for_user(db, current_user.id)


@router.get("/law-firms", response_model=list[LawFirmResponse])
async def list_law_firms(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_verified_user),
):
    return await txn_svc.get_law_firms(db)


@router.get("/{transaction_id}", response_model=TransactionResponse)
async def get_transaction(
    transaction_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_verified_user),
):
    txn = await txn_svc.get_transaction(db, transaction_id)
    if not txn:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Transaction not found")
    _check_access(txn, current_user.id)
    return txn


@router.post("/{transaction_id}/assign-law-firm", response_model=TransactionResponse)
async def assign_law_firm(
    transaction_id: uuid.UUID,
    body: AssignLawFirmRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_verified_user),
):
    txn = await txn_svc.get_transaction(db, transaction_id)
    if not txn:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Transaction not found")
    _check_access(txn, current_user.id)

    if txn.status != TransactionStatus.PENDING_LEGAL:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Law firm can only be assigned in pending_legal status")

    txn = await txn_svc.assign_law_firm(db, txn, body.law_firm_id)
    background_tasks.add_task(
        write_audit_log, action="transaction.law_firm_assigned", user_id=current_user.id,
        resource_type="transaction", resource_id=transaction_id,
        metadata={"law_firm_id": str(body.law_firm_id)},
    )
    return txn


@router.post("/{transaction_id}/draft-contract", response_model=ContractDraftResponse)
@limiter.limit(EXPENSIVE_LIMIT)
async def draft_contract(
    transaction_id: uuid.UUID,
    request: Request,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_verified_user),
):
    txn = await txn_svc.get_transaction(db, transaction_id)
    if not txn:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Transaction not found")
    _check_access(txn, current_user.id)

    contract_text = await txn_svc.draft_contract(db, txn)
    txn = await txn_svc.get_transaction(db, transaction_id)

    background_tasks.add_task(
        write_audit_log, action="transaction.contract_drafted", user_id=current_user.id,
        resource_type="transaction", resource_id=transaction_id,
        metadata={"ai_provider": "anthropic"},
    )
    return ContractDraftResponse(contract_text=contract_text, transaction=txn)


@router.get("/{transaction_id}/contract", response_model=ContractDraftResponse)
async def get_contract(
    transaction_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_verified_user),
):
    """Fetch the stored contract, verifying it against the digest recorded when
    it was drafted. Replaces exposing the raw storage key to clients."""
    txn = await txn_svc.get_transaction(db, transaction_id)
    if not txn:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Transaction not found")
    _check_access(txn, current_user.id)
    return ContractDraftResponse(contract_text=await txn_svc.load_contract(db, txn), transaction=txn)


@router.post("/{transaction_id}/sign", response_model=TransactionResponse)
async def sign_contract(
    transaction_id: uuid.UUID,
    request: Request,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_step_up),
):
    """Record this party's signature.

    The transaction executes only once BOTH parties have signed the same
    contract bytes — one party can no longer bind the other (security/AUDIT.md
    SAHA-008). Requires step-up re-authentication, because execution is what
    unlocks escrow and, transitively, the seller's vault."""
    txn = await txn_svc.get_transaction(db, transaction_id)
    if not txn:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Transaction not found")
    _check_access(txn, current_user.id)

    txn = await txn_svc.sign_contract(
        db, txn, current_user.id,
        ip_address=client_ip(request),
        user_agent=request.headers.get("User-Agent"),
    )
    background_tasks.add_task(
        write_audit_log, action="transaction.contract_signed", user_id=current_user.id,
        resource_type="transaction", resource_id=transaction_id,
        ip_address=client_ip(request), user_agent=request.headers.get("User-Agent"),
        metadata={"contract_sha256": txn.contract_sha256, "status": txn.status.value},
    )
    return txn


@router.get("/{transaction_id}/signatures", response_model=SignatureStatusResponse)
async def signature_status(
    transaction_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_verified_user),
):
    txn = await txn_svc.get_transaction(db, transaction_id)
    if not txn:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Transaction not found")
    _check_access(txn, current_user.id)
    return SignatureStatusResponse(**await txn_svc.signature_status(db, txn))


@router.post("/{transaction_id}/status", response_model=TransactionResponse)
async def update_status(
    transaction_id: uuid.UUID,
    new_status: TransactionStatus,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_verified_user),
):
    """Generic status transition — used for escrow funded, disbursement, completion."""
    txn = await txn_svc.get_transaction(db, transaction_id)
    if not txn:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Transaction not found")
    _check_access(txn, current_user.id)

    txn = await txn_svc.transition_status(db, txn, new_status)
    background_tasks.add_task(
        write_audit_log, action="transaction.status_updated", user_id=current_user.id,
        resource_type="transaction", resource_id=transaction_id,
        metadata={"new_status": new_status.value},
    )
    return txn
