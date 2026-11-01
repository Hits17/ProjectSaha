"""
Stripe webhook handler.
In production this is how escrow funding is confirmed: Stripe sends
payment_intent.succeeded once the buyer's payment clears. Every request is
signature-verified; in mock mode (no real webhook secret) the endpoint refuses
all events — dev flows use the manual /escrow/confirm endpoint instead.
"""

import structlog
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import write_audit_log
from app.db.models.transaction import Transaction, TransactionStatus
from app.db.session import get_db
from app.integrations.stripe_client import verify_webhook_signature
from app.services import settlement as settlement_svc

router = APIRouter(prefix="/api/v1/webhooks", tags=["webhooks"])
logger = structlog.get_logger()


@router.post("/stripe", status_code=200)
async def stripe_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    raw_body = await request.body()
    signature = request.headers.get("Stripe-Signature", "")

    if not verify_webhook_signature(raw_body, signature):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid webhook signature")

    try:
        event = await request.json()
    except Exception:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid JSON payload")

    event_type = event.get("type", "")
    if event_type != "payment_intent.succeeded":
        return {"received": True, "ignored": event_type}

    intent_id = event.get("data", {}).get("object", {}).get("id")
    if not intent_id:
        return {"received": True, "note": "No payment intent id in payload"}

    result = await db.execute(
        select(Transaction).where(Transaction.stripe_payment_intent_id == intent_id)
    )
    txn = result.scalar_one_or_none()
    if not txn:
        logger.warning("stripe_webhook_unmatched_intent", intent_id=intent_id)
        return {"received": True, "note": "No transaction matched payment intent"}

    if txn.status != TransactionStatus.ESCROW_PENDING:
        # Stripe retries deliveries — already-funded transactions are fine to ack
        return {"received": True, "note": f"Transaction already in {txn.status.value}"}

    txn = await settlement_svc.confirm_escrow_funded(db, txn, via_webhook=True)
    background_tasks.add_task(
        write_audit_log, action="settlement.escrow_funded_webhook",
        resource_type="transaction", resource_id=txn.id,
        metadata={"stripe_intent": intent_id},
    )
    logger.info("stripe_escrow_funded", transaction_id=str(txn.id), intent_id=intent_id)
    return {"received": True, "transaction_id": str(txn.id), "status": txn.status.value}
