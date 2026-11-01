"""
Member profiles: LinkedIn-shaped, but with a distinction LinkedIn does not make.

LinkedIn profiles are entirely self-asserted — anyone can claim anything. That is
acceptable when the cost of a false claim is a wasted coffee. On a platform where
a profile informs whether to hand someone unfiled patent claims, the difference
between "they claim" and "we verified" has to be structural, not implied.

So the response is deliberately split:

    verified{}      — derived from platform data. KYC status, completed deals and
                      their ratings, published listings, library contributions,
                      social standing. Nothing here can be typed in by the member.

    self_asserted{} — headline, about, experience, skills, links. Useful, and
                      rendered below the verified block with that framing.

The frontend must not merge these into one section. The split is the feature.
"""

import uuid

from fastapi import HTTPException, status
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.community import CommunityMembership
from app.db.models.listing import IPListing, ListingStatus
from app.db.models.open_resource import OpenResource, OpenResourceStatus
from app.db.models.review import Review
from app.db.models.social import Post, UserProfile
from app.db.models.transaction import Transaction, TransactionStatus
from app.db.models.user import KYCStatus, User
from app.services import posts as post_svc
from app.services import standing as standing_svc

MAX_SKILLS = 50            # LinkedIn's cap
MAX_EXPERIENCE = 25
MAX_FEATURED = 10


async def get_or_create(db: AsyncSession, user_id: uuid.UUID) -> UserProfile:
    profile = await db.get(UserProfile, user_id)
    if profile is None:
        profile = UserProfile(user_id=user_id)
        db.add(profile)
        await db.commit()
        await db.refresh(profile)
    return profile


async def update_profile(db: AsyncSession, user: User, changes: dict) -> UserProfile:
    profile = await get_or_create(db, user.id)

    if "skills" in changes and changes["skills"] is not None:
        skills = [s.strip() for s in changes["skills"] if s and s.strip()]
        if len(skills) > MAX_SKILLS:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                                detail=f"At most {MAX_SKILLS} skills")
        changes["skills"] = skills[:MAX_SKILLS]

    for field in ("experience", "featured"):
        cap = MAX_EXPERIENCE if field == "experience" else MAX_FEATURED
        if changes.get(field) is not None and len(changes[field]) > cap:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                                detail=f"At most {cap} {field} entries")

    for field, value in changes.items():
        if value is not None:
            setattr(profile, field, value)

    await db.commit()
    await db.refresh(profile)
    return profile


async def _verified_block(db: AsyncSession, user: User) -> dict:
    """Platform-derived facts. Nothing here is typed in by the member."""
    completed = await db.scalar(
        select(func.count()).select_from(Transaction).where(
            or_(Transaction.buyer_id == user.id, Transaction.seller_id == user.id),
            Transaction.status == TransactionStatus.COMPLETED,
        )
    ) or 0

    avg_rating, review_count = (await db.execute(
        select(func.avg(Review.rating), func.count(Review.id)).where(Review.reviewee_id == user.id)
    )).one()

    published_listings = await db.scalar(
        select(func.count()).select_from(IPListing).where(
            IPListing.creator_id == user.id, IPListing.status == ListingStatus.PUBLISHED)
    ) or 0

    library_contributions = await db.scalar(
        select(func.count()).select_from(OpenResource).where(
            OpenResource.added_by == user.id,
            OpenResource.status == OpenResourceStatus.APPROVED)
    ) or 0

    communities = await db.scalar(
        select(func.count()).select_from(CommunityMembership).where(
            CommunityMembership.user_id == user.id)
    ) or 0

    return {
        "kyc_verified": user.kyc_status == KYCStatus.VERIFIED,
        "member_since": user.created_at,
        # Track record — expensive to earn, requires real completed deals.
        # Deliberately NOT combined with standing below.
        "completed_deals": int(completed),
        "average_rating": round(float(avg_rating), 2) if avg_rating is not None else None,
        "review_count": int(review_count),
        # Contribution footprint
        "published_listings": int(published_listings),
        "library_contributions": int(library_contributions),
        "communities": int(communities),
    }


async def get_profile(db: AsyncSession, user_id: uuid.UUID, viewer: User | None) -> dict:
    user = await db.get(User, user_id)
    if user is None or not user.is_active:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Member not found")

    profile = await db.get(UserProfile, user_id)
    verified = await _verified_block(db, user)
    social = await standing_svc.get_standing(db, user_id)

    recent_posts = await post_svc.list_feed(db, viewer, author_id=user_id, limit=10)

    return {
        "user_id": user.id,
        "full_name": user.full_name,
        "role": user.role.value,
        "has_avatar": user.avatar_key is not None,

        # Platform-derived. Rendered above the self-asserted block.
        "verified": verified,

        # Social standing. Separate from `verified.completed_deals` /
        # `verified.average_rating` by design — cheap-to-earn engagement must not
        # read as expensive-to-earn trading credibility.
        "standing": social,

        # Self-asserted. Rendered below, framed as claims.
        "self_asserted": {
            "headline": profile.headline if profile else None,
            "about": profile.about if profile else None,
            "location": profile.location if profile else None,
            "website_url": profile.website_url if profile else None,
            "skills": list(profile.skills) if profile and profile.skills else [],
            "experience": (profile.experience if profile else None) or [],
            "featured": (profile.featured if profile else None) or [],
        },

        "recent_posts": recent_posts,
        "is_following": (
            await post_svc.is_following(db, viewer.id, user_id)
            if viewer and viewer.id != user_id else False
        ),
        "is_self": viewer is not None and viewer.id == user_id,
    }
