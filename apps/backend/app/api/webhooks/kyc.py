"""
Persona KYC webhook handler.
In mock mode, signature verification is bypassed.
In production, every request is verified before processing.
"""

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import write_audit_log
from app.db.models.user import KYCStatus, User
from app.db.session import get_db
from app.integrations.kyc import verify_persona_webhook_signature

router = APIRouter(prefix="/api/v1/webhooks", tags=["webhooks"])


@router.post("/kyc", status_code=200)
async def kyc_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    raw_body = await request.body()
    signature = request.headers.get("Persona-Signature", "")

    if not verify_persona_webhook_signature(raw_body, signature):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid webhook signature")

    try:
        payload = await request.json()
    except Exception:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid JSON payload")

    inquiry_id = payload.get("data", {}).get("id")
    events = payload.get("events", [])
    event_name = events[0].get("name") if events else payload.get("data", {}).get("type")

    if not inquiry_id:
        return {"received": True}

    result = await db.execute(select(User).where(User.kyc_inquiry_id == inquiry_id))
    user = result.scalar_one_or_none()

    if not user:
        return {"received": True, "note": "No user matched inquiry_id"}

    if event_name in ("inquiry.approved", "inquiry.completed"):
        user.kyc_status = KYCStatus.VERIFIED
    elif event_name in ("inquiry.failed", "inquiry.declined"):
        user.kyc_status = KYCStatus.REJECTED

    await db.commit()

    background_tasks.add_task(
        write_audit_log,
        action="user.kyc_webhook",
        user_id=user.id,
        resource_type="user",
        resource_id=user.id,
        metadata={"event": event_name, "inquiry_id": inquiry_id, "new_status": user.kyc_status.value},
    )

    return {"received": True, "user_id": str(user.id), "kyc_status": user.kyc_status.value}
