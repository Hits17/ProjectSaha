import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas.review import ReputationResponse, ReviewCreate, ReviewResponse
from app.core.audit import write_audit_log
from app.core.security import require_verified_user
from app.db.models.user import User
from app.db.session import get_db
from app.services import reviews as review_svc
from app.services.transactions import get_transaction

router = APIRouter(prefix="/api/v1", tags=["reviews"])


@router.post("/transactions/{transaction_id}/reviews", response_model=ReviewResponse, status_code=status.HTTP_201_CREATED)
async def create_review(
    transaction_id: uuid.UUID,
    body: ReviewCreate,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_verified_user),
):
    txn = await get_transaction(db, transaction_id)
    if not txn:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Transaction not found")

    review = await review_svc.create_review(db, txn, current_user.id, body.rating, body.comment)
    background_tasks.add_task(
        write_audit_log, action="review.created", user_id=current_user.id,
        resource_type="transaction", resource_id=transaction_id,
        metadata={"rating": body.rating, "reviewee_id": str(review.reviewee_id)},
    )
    return review


@router.get("/transactions/{transaction_id}/reviews", response_model=list[ReviewResponse])
async def list_transaction_reviews(
    transaction_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_verified_user),
):
    txn = await get_transaction(db, transaction_id)
    if not txn:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Transaction not found")
    if current_user.id not in (txn.buyer_id, txn.seller_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not a party to this transaction")
    return await review_svc.get_reviews_for_transaction(db, transaction_id)


@router.get("/users/{user_id}/reputation", response_model=ReputationResponse)
async def get_user_reputation(
    user_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_verified_user),
):
    return await review_svc.get_reputation(db, user_id)
