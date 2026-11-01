"""
Reviews service: post-transaction reputation. A party to a COMPLETED transaction
may leave exactly one review of the counterparty.
"""

import uuid

import structlog
from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.review import Review
from app.db.models.transaction import Transaction, TransactionStatus

logger = structlog.get_logger()


async def create_review(
    db: AsyncSession,
    transaction: Transaction,
    reviewer_id: uuid.UUID,
    rating: int,
    comment: str | None,
) -> Review:
    if transaction.status != TransactionStatus.COMPLETED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Reviews can only be left on completed transactions (current: {transaction.status.value})",
        )

    if reviewer_id == transaction.buyer_id:
        reviewee_id = transaction.seller_id
    elif reviewer_id == transaction.seller_id:
        reviewee_id = transaction.buyer_id
    else:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not a party to this transaction")

    existing = await db.execute(
        select(Review).where(
            Review.transaction_id == transaction.id,
            Review.reviewer_id == reviewer_id,
        )
    )
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="You have already reviewed this transaction",
        )

    review = Review(
        transaction_id=transaction.id,
        reviewer_id=reviewer_id,
        reviewee_id=reviewee_id,
        rating=rating,
        comment=comment,
    )
    db.add(review)
    await db.commit()
    await db.refresh(review)

    from app.core import metrics
    metrics.reviews_created_total.inc()

    logger.info("review_created", transaction_id=str(transaction.id), reviewer=str(reviewer_id), rating=rating)
    return review


async def get_reviews_for_transaction(db: AsyncSession, transaction_id: uuid.UUID) -> list[Review]:
    result = await db.execute(
        select(Review).where(Review.transaction_id == transaction_id).order_by(Review.created_at.desc())
    )
    return list(result.scalars().all())


async def get_reputation(db: AsyncSession, user_id: uuid.UUID) -> dict:
    """Average rating, count, and the most recent reviews received by a user."""
    agg = await db.execute(
        select(func.avg(Review.rating), func.count(Review.id)).where(Review.reviewee_id == user_id)
    )
    avg_rating, count = agg.one()

    recent = await db.execute(
        select(Review)
        .where(Review.reviewee_id == user_id)
        .order_by(Review.created_at.desc())
        .limit(20)
    )
    reviews = list(recent.scalars().all())

    return {
        "user_id": user_id,
        "average_rating": round(float(avg_rating), 2) if avg_rating is not None else None,
        "review_count": int(count),
        "reviews": reviews,
    }
