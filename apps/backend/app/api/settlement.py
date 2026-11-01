import uuid
from urllib.parse import quote

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, status
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas.transaction import DisburseRequest, TransactionResponse
from app.core.audit import write_audit_log
from app.core.clientip import client_ip
from app.core.ratelimit import MONEY_LIMIT, VAULT_DOWNLOAD_LIMIT, limiter
from app.core.security import require_step_up, require_verified_user
from app.services import notifications as notif_svc
from app.db.models.user import User, UserRole
from app.db.session import get_db
from app.services import settlement as settlement_svc
from app.services.transactions import get_transaction

router = APIRouter(prefix="/api/v1/transactions", tags=["settlement"])


def _check_access(txn, user_id: uuid.UUID) -> None:
    if txn.buyer_id != user_id and txn.seller_id != user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not a party to this transaction")


def _check_buyer(txn, user_id: uuid.UUID) -> None:
    if txn.buyer_id != user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only the buyer can fund escrow")


@router.post("/{transaction_id}/escrow/create", response_model=TransactionResponse)
@limiter.limit(MONEY_LIMIT)
async def create_escrow(
    transaction_id: uuid.UUID,
    request: Request,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_verified_user),
):
    txn = await get_transaction(db, transaction_id)
    if not txn:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Transaction not found")
    _check_buyer(txn, current_user.id)

    txn = await settlement_svc.create_escrow(db, txn)
    background_tasks.add_task(
        write_audit_log, action="settlement.escrow_created", user_id=current_user.id,
        resource_type="transaction", resource_id=transaction_id,
        metadata={"stripe_intent": txn.stripe_payment_intent_id},
    )
    return txn


@router.post("/{transaction_id}/escrow/confirm", response_model=TransactionResponse)
@limiter.limit(MONEY_LIMIT)
async def confirm_escrow(
    transaction_id: uuid.UUID,
    request: Request,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_verified_user),
):
    """Confirm escrow funded — in production triggered by Stripe webhook; in dev/mock call this directly."""
    txn = await get_transaction(db, transaction_id)
    if not txn:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Transaction not found")
    _check_buyer(txn, current_user.id)

    txn = await settlement_svc.confirm_escrow_funded(db, txn)
    background_tasks.add_task(
        write_audit_log, action="settlement.escrow_funded", user_id=current_user.id,
        resource_type="transaction", resource_id=transaction_id, metadata={},
    )
    background_tasks.add_task(
        notif_svc.notify, txn.seller_id,
        "settlement.escrow_funded", "Escrow funded",
        "The buyer has funded escrow — the deal can proceed to disbursement.",
        f"/dashboard/transactions/{transaction_id}",
    )
    return txn


@router.post("/{transaction_id}/disburse", response_model=TransactionResponse)
@limiter.limit(MONEY_LIMIT)
async def disburse(
    transaction_id: uuid.UUID,
    request: Request,
    background_tasks: BackgroundTasks,
    body: DisburseRequest | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_step_up),
):
    """Release escrow to the seller.

    Buyer-only: this is the payer's decision about the payer's money. An admin
    may release when resolving a dispute. Requires step-up re-authentication —
    escrow release is irreversible, so a stolen access token alone must not be
    enough to trigger it."""
    txn = await get_transaction(db, transaction_id)
    if not txn:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Transaction not found")
    _check_access(txn, current_user.id)
    settlement_svc._assert_may_release(
        txn, current_user.id, actor_is_admin=current_user.role == UserRole.ADMIN
    )

    txn = await settlement_svc.disburse(
        db, txn, released_by=current_user.id, reason=body.reason if body else None
    )
    background_tasks.add_task(
        write_audit_log, action="settlement.disbursed", user_id=current_user.id,
        resource_type="transaction", resource_id=transaction_id,
        ip_address=client_ip(request),
        metadata={
            "status": txn.status.value,
            "released_by": str(current_user.id),
            "reason": body.reason if body else None,
        },
    )
    # Notify both parties that funds have been disbursed and the deal completed.
    for party in {txn.buyer_id, txn.seller_id}:
        background_tasks.add_task(
            notif_svc.notify, party,
            "settlement.disbursed", "Funds disbursed",
            "Escrow has been disbursed and the transaction is complete.",
            f"/dashboard/transactions/{transaction_id}",
        )
    return txn


@router.get("/{transaction_id}/vault-access")
async def vault_access_files(
    transaction_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_verified_user),
):
    txn = await get_transaction(db, transaction_id)
    if not txn:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Transaction not found")

    return await settlement_svc.get_vault_access_files(db, txn, current_user.id)


@router.get("/{transaction_id}/vault-access/{asset_id}/download")
@limiter.limit(VAULT_DOWNLOAD_LIMIT)
async def download_vault_asset(
    transaction_id: uuid.UUID,
    asset_id: uuid.UUID,
    request: Request,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_step_up),
):
    """Streams the decrypted vault file to an authorized party.

    This is the platform's most sensitive egress point: it emits a seller's
    confidential IP documents in plaintext. It therefore requires step-up
    re-authentication, is rate-limited so a bulk pull is throttled and visible,
    and every download is audited into the tamper-evident chain."""
    txn = await get_transaction(db, transaction_id)
    if not txn:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Transaction not found")

    filename, content_type, data = await settlement_svc.download_vault_asset(
        db, txn, current_user.id, asset_id
    )
    background_tasks.add_task(
        write_audit_log, action="vault.file_downloaded", user_id=current_user.id,
        resource_type="transaction", resource_id=transaction_id,
        ip_address=client_ip(request), user_agent=request.headers.get("User-Agent"),
        metadata={"asset_id": str(asset_id), "filename": filename, "bytes": len(data)},
    )
    # Sanitize the filename for the Content-Disposition header: strip quotes and
    # any control chars (CR/LF would enable header injection), keep a plain-ASCII
    # fallback, and provide the exact name via RFC 5987 filename* for modern clients.
    ascii_name = "".join(c for c in filename if 32 <= ord(c) < 127 and c not in '"\\/') or "download"
    quoted = quote(filename, safe="")
    return Response(
        content=data,
        media_type=content_type,
        headers={
            "Content-Disposition": (
                f'attachment; filename="{ascii_name}"; filename*=UTF-8\'\'{quoted}'
            )
        },
    )
