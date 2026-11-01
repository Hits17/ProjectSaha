"""
Settlement service: escrow creation, confirmation, disbursement, and vault access release.
"""

import uuid
from datetime import datetime, timezone
from decimal import Decimal

import structlog
from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.models.transaction import Disbursement, Transaction, TransactionStatus
from app.integrations import stripe_client
from app.services.transactions import get_transaction

logger = structlog.get_logger()


async def create_escrow(db: AsyncSession, transaction: Transaction) -> Transaction:
    """Create a Stripe PaymentIntent for the escrow amount."""
    if transaction.status != TransactionStatus.SIGNED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Escrow can only be created after contract is signed (current: {transaction.status.value})"
        )

    ds = transaction.deal_summary or {}
    intent = await stripe_client.create_payment_intent(
        amount_usd=float(transaction.deal_value_usd),
        metadata={
            "transaction_id": str(transaction.id),
            "listing_title": ds.get("listing_title", ""),
            "buyer_id": str(transaction.buyer_id),
            "seller_id": str(transaction.seller_id),
        },
    )

    transaction.stripe_payment_intent_id = intent["id"]
    transaction.status = TransactionStatus.ESCROW_PENDING
    await db.commit()
    return await get_transaction(db, transaction.id)


async def confirm_escrow_funded(
    db: AsyncSession, transaction: Transaction, via_webhook: bool = False
) -> Transaction:
    """Mark escrow as funded (triggered by Stripe webhook or mock confirm)."""
    if transaction.status != TransactionStatus.ESCROW_PENDING:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Transaction must be in escrow_pending status (current: {transaction.status.value})"
        )

    # Funding is proven only by the signature-verified payment_intent.succeeded
    # webhook. The manual buyer endpoint may simulate confirmation only in
    # development; anywhere else it must not mark escrow funded without money
    # actually moving, because escrow_funded is what releases the seller's vault
    # to the buyer (security/AUDIT.md SAHA-036).
    if stripe_client.is_mock_mode():
        if transaction.stripe_payment_intent_id:
            await stripe_client.confirm_payment_intent(transaction.stripe_payment_intent_id)
    elif not via_webhook:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Escrow funding is confirmed automatically once the Stripe payment succeeds",
        )

    transaction.status = TransactionStatus.ESCROW_FUNDED
    transaction.escrow_funded_at = datetime.now(timezone.utc)
    await db.commit()
    return await get_transaction(db, transaction.id)


async def _lock_transaction(db: AsyncSession, transaction_id: uuid.UUID) -> Transaction:
    """Re-read the transaction under a row lock.

    Every state check in this module is read-modify-write. Without a lock, two
    concurrent calls both observe ESCROW_FUNDED and both proceed — producing two
    disbursements for one escrow (security/AUDIT.md SAHA-032). The lock is held
    to the end of the transaction, so the second caller sees the committed new
    status and fails its precondition check instead.
    """
    from sqlalchemy import select

    row = await db.execute(
        select(Transaction).where(Transaction.id == transaction_id).with_for_update()
    )
    txn = row.scalar_one_or_none()
    if txn is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Transaction not found")
    return txn


async def disburse(
    db: AsyncSession, transaction: Transaction, released_by: uuid.UUID, reason: str | None = None
) -> Transaction:
    """
    Release escrow. Callable only by the buyer (the payer) or an admin — see
    `_assert_may_release`.

    - IP holder receives: deal_value - commission - legal_fee - escrow_fee
    - Saha receives: commission
    - Law firm receives: legal_fee
    - Escrow fee: retained
    """
    # Re-read under a row lock so a concurrent call cannot also observe
    # ESCROW_FUNDED and disburse a second time.
    transaction = await _lock_transaction(db, transaction.id)

    if transaction.status != TransactionStatus.ESCROW_FUNDED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Funds must be in escrow before disbursement (current: {transaction.status.value})"
        )

    deal = transaction.deal_value_usd
    commission = transaction.saha_commission_usd or Decimal("0")
    legal_fee = transaction.legal_fee_usd or Decimal("0")
    escrow_fee = transaction.escrow_fee_usd or Decimal("0")
    ip_holder_amount = deal - commission - legal_fee - escrow_fee
    if ip_holder_amount < 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Fees exceed the deal value — disbursement blocked pending manual review",
        )

    transfer_ids = {}

    # Transfer to IP holder (seller) — mock uses seller_id as destination
    if ip_holder_amount > 0:
        seller_transfer = await stripe_client.create_transfer(
            float(ip_holder_amount),
            destination=f"acct_{str(transaction.seller_id)[:16]}",
            metadata={"transaction_id": str(transaction.id), "type": "ip_holder"},
        )
        transfer_ids["ip_holder"] = seller_transfer["id"]

    # Transfer to law firm (if assigned)
    if legal_fee > 0 and transaction.law_firm_id:
        firm_transfer = await stripe_client.create_transfer(
            float(legal_fee),
            destination=f"acct_lawfirm_{str(transaction.law_firm_id)[:12]}",
            metadata={"transaction_id": str(transaction.id), "type": "legal_fee"},
        )
        transfer_ids["law_firm"] = firm_transfer["id"]

    disbursement = Disbursement(
        transaction_id=transaction.id,
        ip_holder_amount_usd=ip_holder_amount,
        saha_commission_usd=commission,
        legal_fee_usd=legal_fee,
        escrow_fee_usd=escrow_fee,
        stripe_transfer_ids=transfer_ids,
        released_by_id=released_by,
        release_reason=reason,
        executed_at=datetime.now(timezone.utc),
    )
    db.add(disbursement)

    transaction.status = TransactionStatus.COMPLETED
    transaction.disbursed_at = datetime.now(timezone.utc)
    await db.commit()

    from app.core import metrics
    metrics.transactions_completed_total.inc()
    metrics.disbursed_usd_total.inc(float(ip_holder_amount))
    metrics.commission_usd_total.inc(float(commission))

    logger.info(
        "disbursement_complete",
        transaction_id=str(transaction.id),
        ip_holder_amount=str(ip_holder_amount),
        commission=str(commission),
    )

    return await get_transaction(db, transaction.id)


_FUNDED_STATUSES = {
    TransactionStatus.ESCROW_FUNDED,
    TransactionStatus.DISBURSEMENT_PENDING,
    TransactionStatus.COMPLETED,
}


def _assert_may_release(transaction: Transaction, actor_id: uuid.UUID, actor_is_admin: bool) -> None:
    """Only the payer releases escrow — or an admin resolving a dispute.

    This previously used the either-party predicate, which let the **seller**
    transfer the escrow to themselves the moment the buyer funded it, with no
    approval, inspection period or dispute window (security/AUDIT.md SAHA-007).
    Release is the buyer's decision because release is the buyer's money.

    The longer-term answer is a licensed escrow agent with contractual release
    conditions and a timed auto-release (ROADMAP §4.2); this is the correct
    predicate until then.
    """
    if actor_is_admin:
        return
    if transaction.buyer_id != actor_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                "Only the buyer can release escrow. If the buyer is unresponsive, "
                "raise a dispute for admin resolution."
            ),
        )


def _assert_vault_access(transaction: Transaction, requesting_user_id: uuid.UUID) -> None:
    """Seller always has access to their own IP; buyer only once escrow is funded."""
    if transaction.buyer_id != requesting_user_id and transaction.seller_id != requesting_user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not a party to this transaction")

    is_seller = transaction.seller_id == requesting_user_id
    if is_seller:
        return

    if transaction.status not in _FUNDED_STATUSES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Vault access is granted to the buyer after escrow is funded"
        )

    # Defence in depth: the status alone is not evidence that money moved. A bug
    # or a manual status change that reached ESCROW_FUNDED without funding would
    # otherwise release the seller's confidential documents. Outside development,
    # require the funding artefacts to exist too (SAHA-036).
    if not settings.allows_mock_integrations:
        if transaction.escrow_funded_at is None or not transaction.stripe_payment_intent_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Vault access requires confirmed escrow funding",
            )


async def get_vault_access_files(db: AsyncSession, transaction: Transaction, requesting_user_id: uuid.UUID) -> list[dict]:
    """
    List vault files the requesting party may download. Files are AES-256-GCM
    encrypted at rest, so access goes through the authenticated download endpoint
    (which decrypts) — never through raw storage URLs.
    """
    _assert_vault_access(transaction, requesting_user_id)

    from app.db.models.listing import IPVaultAsset
    from sqlalchemy import select
    result = await db.execute(
        select(IPVaultAsset).where(IPVaultAsset.listing_id == transaction.listing_id)
    )
    assets = result.scalars().all()

    return [
        {
            "asset_id": str(asset.id),
            "filename": asset.original_filename,
            "file_size_bytes": asset.file_size_bytes,
            "content_type": asset.content_type,
            "download_path": f"/api/v1/transactions/{transaction.id}/vault-access/{asset.id}/download",
        }
        for asset in assets
    ]


async def download_vault_asset(
    db: AsyncSession,
    transaction: Transaction,
    requesting_user_id: uuid.UUID,
    asset_id: uuid.UUID,
) -> tuple[str, str, bytes]:
    """Decrypt one vault asset for an authorized party. Returns (filename, content_type, data)."""
    _assert_vault_access(transaction, requesting_user_id)

    from app.db.models.listing import IPVaultAsset
    from sqlalchemy import select
    result = await db.execute(
        select(IPVaultAsset).where(
            IPVaultAsset.id == asset_id,
            IPVaultAsset.listing_id == transaction.listing_id,
        )
    )
    asset = result.scalar_one_or_none()
    if not asset:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Vault asset not found")

    from app.services.vault import content_digest, decrypt_file
    data = await decrypt_file(asset.storage_key, asset.encryption_key_id or "v1")

    # Integrity check against the digest recorded at ingest. AES-GCM already
    # authenticates the ciphertext, so this catches the different failure: an
    # object swapped wholesale in storage, re-encrypted under a key we hold.
    if asset.content_sha256 and content_digest(data) != asset.content_sha256:
        logger.error("vault_asset_integrity_mismatch", asset_id=str(asset.id),
                     storage_key=asset.storage_key)
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Document integrity check failed — this file has been reported to the operator.",
        )

    return asset.original_filename, asset.content_type or "application/octet-stream", data
