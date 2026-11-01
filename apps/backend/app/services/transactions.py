"""
Legal Workspace service.
Flow: proposal accepted → transaction created → law firm assigned →
      contract drafted (Anthropic) → stored in MinIO → DocuSign (or mock) → escrow → complete.
"""

import uuid
from decimal import Decimal, ROUND_HALF_UP

import structlog
from fastapi import HTTPException, status
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.ai.client import Message, llm
from app.core.config import settings
from app.db.models.listing import IPListing
from app.db.models.proposal import Proposal
from app.db.models.transaction import (
    ContractSignature, Disbursement, LawFirmPartner, Transaction, TransactionStatus,
)
from app.db.models.user import User

logger = structlog.get_logger()

SAHA_COMMISSION_RATE = Decimal("0.05")   # 5%
ESCROW_FEE_RATE = Decimal("0.01")        # 1%
DEFAULT_LEGAL_FEE_RATE = Decimal("0.03") # 3%

_VALID_TRANSITIONS: dict[TransactionStatus, set[TransactionStatus]] = {
    TransactionStatus.PENDING_LEGAL:       {TransactionStatus.CONTRACT_DRAFTING, TransactionStatus.CANCELLED},
    TransactionStatus.CONTRACT_DRAFTING:   {TransactionStatus.CONTRACT_REVIEW, TransactionStatus.CANCELLED},
    TransactionStatus.CONTRACT_REVIEW:     {TransactionStatus.SIGNING_PENDING, TransactionStatus.CONTRACT_DRAFTING},
    TransactionStatus.SIGNING_PENDING:     {TransactionStatus.SIGNED, TransactionStatus.CANCELLED},
    TransactionStatus.SIGNED:              {TransactionStatus.ESCROW_PENDING},
    TransactionStatus.ESCROW_PENDING:      {TransactionStatus.ESCROW_FUNDED, TransactionStatus.CANCELLED},
    TransactionStatus.ESCROW_FUNDED:       {TransactionStatus.DISBURSEMENT_PENDING},
    TransactionStatus.DISBURSEMENT_PENDING:{TransactionStatus.COMPLETED},
    TransactionStatus.COMPLETED:           set(),
    TransactionStatus.DISPUTED:            {TransactionStatus.COMPLETED, TransactionStatus.CANCELLED},
    TransactionStatus.CANCELLED:           set(),
}

# Statuses only the settlement/signing services may set. Reaching them through the
# generic status endpoint would let a party mark escrow as funded (or the deal as
# completed) without any money moving.
_SYSTEM_ONLY_TARGETS = {
    TransactionStatus.SIGNED,
    TransactionStatus.ESCROW_PENDING,
    TransactionStatus.ESCROW_FUNDED,
    TransactionStatus.DISBURSEMENT_PENDING,
    TransactionStatus.COMPLETED,
}

# Once a deal reaches any of these, the asset is committed and no other deal on
# the same listing may be executed. IP is not fungible — see
# assert_no_competing_deal (security/AUDIT.md SAHA-037).
_EXCLUSIVE_STATUSES = {
    TransactionStatus.SIGNED,
    TransactionStatus.ESCROW_PENDING,
    TransactionStatus.ESCROW_FUNDED,
    TransactionStatus.DISBURSEMENT_PENDING,
    TransactionStatus.COMPLETED,
}


async def get_transaction(db: AsyncSession, transaction_id: uuid.UUID) -> Transaction | None:
    result = await db.execute(
        select(Transaction)
        .options(selectinload(Transaction.law_firm), selectinload(Transaction.disbursements))
        .where(Transaction.id == transaction_id)
        .execution_options(populate_existing=True)
    )
    return result.scalar_one_or_none()


async def get_transactions_for_user(db: AsyncSession, user_id: uuid.UUID) -> list[Transaction]:
    from sqlalchemy import or_
    result = await db.execute(
        select(Transaction)
        .options(selectinload(Transaction.law_firm), selectinload(Transaction.disbursements))
        .where(or_(Transaction.buyer_id == user_id, Transaction.seller_id == user_id))
        .order_by(Transaction.updated_at.desc())
    )
    return list(result.scalars().all())


async def get_law_firms(db: AsyncSession) -> list[LawFirmPartner]:
    result = await db.execute(
        select(LawFirmPartner).where(LawFirmPartner.is_active == True).order_by(LawFirmPartner.name)
    )
    return list(result.scalars().all())


async def create_from_proposal(db: AsyncSession, proposal: Proposal) -> Transaction:
    """Auto-called when a proposal is accepted. Computes fees and creates the transaction."""
    deal_value = proposal.offer_amount_usd or Decimal("0")
    commission = (deal_value * SAHA_COMMISSION_RATE).quantize(Decimal("0.01"), ROUND_HALF_UP)
    legal_fee = (deal_value * DEFAULT_LEGAL_FEE_RATE).quantize(Decimal("0.01"), ROUND_HALF_UP)
    escrow_fee = (deal_value * ESCROW_FEE_RATE).quantize(Decimal("0.01"), ROUND_HALF_UP)

    listing = await db.get(IPListing, proposal.listing_id)
    buyer = await db.get(User, proposal.buyer_id)
    seller = await db.get(User, proposal.seller_id)

    deal_summary = {
        "listing_title": listing.title if listing else str(proposal.listing_id),
        "buyer_name": buyer.full_name if buyer else str(proposal.buyer_id),
        "seller_name": seller.full_name if seller else str(proposal.seller_id),
        "license_type": proposal.license_type,
        "territory": proposal.territory,
        "duration_months": proposal.duration_months,
        "offer_amount_usd": str(deal_value),
        "proposal_version": proposal.version,
    }

    transaction = Transaction(
        proposal_id=proposal.id,
        listing_id=proposal.listing_id,
        buyer_id=proposal.buyer_id,
        seller_id=proposal.seller_id,
        status=TransactionStatus.PENDING_LEGAL,
        deal_value_usd=deal_value,
        saha_commission_usd=commission,
        legal_fee_usd=legal_fee,
        escrow_fee_usd=escrow_fee,
        deal_summary=deal_summary,
    )
    db.add(transaction)
    await db.commit()

    from app.core import metrics
    metrics.transactions_created_total.inc()
    metrics.deal_value_usd.observe(float(deal_value))

    return await get_transaction(db, transaction.id)


async def assign_law_firm(db: AsyncSession, transaction: Transaction, law_firm_id: uuid.UUID) -> Transaction:
    firm = await db.get(LawFirmPartner, law_firm_id)
    if not firm or not firm.is_active:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Law firm not found or inactive")

    transaction.law_firm_id = law_firm_id
    transaction.status = TransactionStatus.CONTRACT_DRAFTING
    await db.commit()
    return await get_transaction(db, transaction.id)


async def assert_no_competing_deal(db: AsyncSession, listing_id: uuid.UUID, exclude_id: uuid.UUID) -> None:
    """Refuse to advance a deal while another on the same asset is already live.

    Nothing previously prevented a seller running parallel transactions on one
    listing to ESCROW_FUNDED with several buyers — each of whom would then be
    released the vault, and each of whom would pay (security/AUDIT.md SAHA-037).
    IP is not fungible; two buyers cannot both acquire the same exclusive right.

    Applied at the point of execution rather than at proposal time, so
    competitive bidding still works: many proposals may be open, but only one
    may proceed past signature.
    """
    live = await db.execute(
        select(Transaction.id).where(
            Transaction.listing_id == listing_id,
            Transaction.id != exclude_id,
            Transaction.status.in_(_EXCLUSIVE_STATUSES),
        )
    )
    if live.scalars().first():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Another transaction on this listing has already been executed. "
                "Only one deal per asset can proceed past signature."
            ),
        )


async def draft_contract(db: AsyncSession, transaction: Transaction) -> str:
    """Uses Anthropic (via legal_concept_assistant) to draft an IP license agreement."""
    if transaction.status != TransactionStatus.CONTRACT_DRAFTING:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Contract drafting only available in contract_drafting status (current: {transaction.status.value})"
        )

    ds = transaction.deal_summary or {}
    prompt = f"""Draft a professional IP License Agreement based on these terms:

- IP Asset: {ds.get("listing_title", "Proprietary Technology")}
- Licensor (Seller): {ds.get("seller_name", "Seller")}
- Licensee (Buyer): {ds.get("buyer_name", "Buyer")}
- License Type: {ds.get("license_type", "Non-exclusive")}
- Territory: {ds.get("territory", "Global")}
- Duration: {ds.get("duration_months", 12)} months
- License Fee: USD {ds.get("offer_amount_usd", "0")}
- Platform Commission: USD {transaction.saha_commission_usd} (paid to Saha)
- Legal Fee: USD {transaction.legal_fee_usd}

Include standard clauses: definitions, grant of license, payment terms,
confidentiality, IP ownership, representations and warranties,
indemnification, termination, governing law (Delaware, USA).
Mark placeholders for signatures with [SIGNATURE BLOCK].
Keep it professional and enforceable."""

    response = await llm.complete(
        messages=[Message(role="user", content=prompt)],
        function_name="legal_concept_assistant",
        temperature=0.2,
        max_tokens=4000,
    )

    contract_text = response.content
    contract_bytes = contract_text.encode()

    # Contracts are encrypted at rest like vault assets, and their plaintext
    # digest is recorded. Previously they were written as plaintext .txt into the
    # same bucket as the encrypted vault, unhashed — readable by anyone with
    # storage access and replaceable in place after signing, with no trace
    # (security/AUDIT.md SAHA-021).
    from app.integrations import storage
    from app.services.vault import KEY_VERSION, _encrypt, content_digest

    key = f"contracts/{transaction.id}/draft.txt.enc"
    await storage.upload_file(key, _encrypt(contract_bytes), "application/octet-stream")
    transaction.contract_storage_key = key
    transaction.contract_sha256 = content_digest(contract_bytes)
    transaction.contract_encryption_key_id = KEY_VERSION
    transaction.status = TransactionStatus.CONTRACT_REVIEW

    # A redraft invalidates any signature already collected: those parties signed
    # different words. Clearing them is the honest behaviour — silently keeping
    # them would let one party alter agreed terms after the other had signed.
    await db.execute(
        delete(ContractSignature).where(ContractSignature.transaction_id == transaction.id)
    )
    await db.commit()

    return contract_text


async def load_contract(db: AsyncSession, transaction: Transaction) -> str:
    """Fetch and verify the stored contract."""
    if not transaction.contract_storage_key:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No contract drafted yet")

    from app.integrations.storage import _s3_client
    from app.services.vault import _decrypt, content_digest

    async with _s3_client() as s3:
        resp = await s3.get_object(
            Bucket=settings.MINIO_BUCKET, Key=transaction.contract_storage_key
        )
        async with resp["Body"] as stream:
            blob = await stream.read()

    # Contracts written before this migration are plaintext and carry no key
    # version. They stay readable — the fix is forward-looking, and breaking
    # access to an existing deal's contract would be a worse outcome than the
    # storage exposure it already has. Redrafting re-writes them encrypted.
    if transaction.contract_encryption_key_id:
        plaintext = _decrypt(blob, transaction.contract_encryption_key_id)
    else:
        logger.warning("legacy_plaintext_contract_read", transaction_id=str(transaction.id))
        plaintext = blob

    if transaction.contract_sha256 and content_digest(plaintext) != transaction.contract_sha256:
        logger.error("contract_integrity_mismatch", transaction_id=str(transaction.id))
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Contract integrity check failed — the stored document does not match what was signed.",
        )
    return plaintext.decode()


async def sign_contract(
    db: AsyncSession,
    transaction: Transaction,
    signer_id: uuid.UUID,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> Transaction:
    """Record one party's signature; execute only when both have signed.

    The previous implementation flipped the transaction to SIGNED whenever
    *either* party called it, recorded nothing about who signed, and left the
    DocuSign envelope id permanently NULL — so one party could unilaterally
    reach the state that unlocks escrow and, transitively, the counterparty's
    vault, and either party could later deny having agreed with nothing to
    contradict them (security/AUDIT.md SAHA-008).

    Each signature is bound to the SHA-256 of the contract bytes, so a contract
    swapped after signing fails verification instead of passing silently. This
    is an interim measure: the operative artefact should be a real e-signature
    envelope (ROADMAP §4.1), and what constitutes valid execution differs by
    jurisdiction — counsel's call, not this function's.
    """
    if transaction.status != TransactionStatus.CONTRACT_REVIEW:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Contract must be in review to sign (current: {transaction.status.value})"
        )
    if signer_id not in (transaction.buyer_id, transaction.seller_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not a party to this transaction")
    if not transaction.contract_sha256:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Draft the contract before signing",
        )

    # Confirm the stored document still matches what will be signed.
    await load_contract(db, transaction)

    existing = await db.execute(
        select(ContractSignature).where(
            ContractSignature.transaction_id == transaction.id,
            ContractSignature.signer_id == signer_id,
        )
    )
    if existing.scalar_one_or_none() is None:
        db.add(
            ContractSignature(
                transaction_id=transaction.id,
                signer_id=signer_id,
                contract_sha256=transaction.contract_sha256,
                ip_address=ip_address,
                user_agent=user_agent,
            )
        )
        await db.flush()

    signed_by = set(
        (await db.execute(
            select(ContractSignature.signer_id).where(
                ContractSignature.transaction_id == transaction.id,
                ContractSignature.contract_sha256 == transaction.contract_sha256,
            )
        )).scalars().all()
    )

    if {transaction.buyer_id, transaction.seller_id} <= signed_by:
        # Both parties have executed. Check no competing deal beat us to it
        # before this asset is committed.
        await assert_no_competing_deal(db, transaction.listing_id, transaction.id)
        transaction.status = TransactionStatus.SIGNED
        logger.info("contract_fully_executed", transaction_id=str(transaction.id))
    else:
        logger.info(
            "contract_partially_signed",
            transaction_id=str(transaction.id),
            signatures=len(signed_by),
        )

    await db.commit()
    return await get_transaction(db, transaction.id)


async def signature_status(db: AsyncSession, transaction: Transaction) -> dict:
    rows = (await db.execute(
        select(ContractSignature).where(ContractSignature.transaction_id == transaction.id)
    )).scalars().all()
    signed_by = {r.signer_id for r in rows if r.contract_sha256 == transaction.contract_sha256}
    return {
        "contract_sha256": transaction.contract_sha256,
        "buyer_signed": transaction.buyer_id in signed_by,
        "seller_signed": transaction.seller_id in signed_by,
        "fully_executed": {transaction.buyer_id, transaction.seller_id} <= signed_by,
        "signatures": [
            {"signer_id": str(r.signer_id), "signed_at": r.signed_at.isoformat()}
            for r in rows
        ],
    }


async def transition_status(
    db: AsyncSession,
    transaction: Transaction,
    new_status: TransactionStatus,
    requested_by_user: bool = True,
) -> Transaction:
    allowed = _VALID_TRANSITIONS.get(transaction.status, set())
    if new_status not in allowed:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot transition from {transaction.status.value} to {new_status.value}",
        )
    if requested_by_user and new_status in _SYSTEM_ONLY_TARGETS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Status '{new_status.value}' is set by the signing/settlement flow, not directly",
        )
    transaction.status = new_status
    await db.commit()
    return await get_transaction(db, transaction.id)
