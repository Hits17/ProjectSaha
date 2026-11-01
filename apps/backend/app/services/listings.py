"""
Listing service: create, query, BOM finalization, publish.
"""

import json
import re
import uuid
from decimal import Decimal

import structlog
from fastapi import HTTPException, status
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.ai import sessions as ai_sessions
from app.ai.client import Message, llm
from app.ai.prompts.bom_creator import FINALIZE_PROMPT, SYSTEM_PROMPT
from app.db.models.listing import BOMItem, IPListing, IPVaultAsset, ListingStatus
from app.services import embeddings

logger = structlog.get_logger()


async def create_listing(
    db: AsyncSession,
    creator_id: uuid.UUID,
    title: str,
    product_category: str | None = None,
    description: str | None = None,
) -> IPListing:
    listing = IPListing(
        creator_id=creator_id,
        title=title,
        product_category=product_category,
        description=description,
    )
    db.add(listing)
    await db.commit()
    await db.refresh(listing)
    return listing


async def get_listing(db: AsyncSession, listing_id: uuid.UUID) -> IPListing | None:
    result = await db.execute(
        select(IPListing)
        .options(selectinload(IPListing.bom_items), selectinload(IPListing.vault_assets))
        .where(IPListing.id == listing_id)
        .execution_options(populate_existing=True)
    )
    return result.scalar_one_or_none()


async def get_creator_listings(db: AsyncSession, creator_id: uuid.UUID) -> list[IPListing]:
    result = await db.execute(
        select(IPListing)
        .options(selectinload(IPListing.bom_items), selectinload(IPListing.vault_assets))
        .where(IPListing.creator_id == creator_id)
        .order_by(IPListing.created_at.desc())
    )
    return list(result.scalars().all())


_VIEW_DEDUPE_TTL = 3600  # one counted view per viewer per listing per hour


async def record_view(db: AsyncSession, listing_id: uuid.UUID, viewer_id: uuid.UUID | None) -> None:
    """Increment a listing's view count, at most once per viewer per hour.

    The counter previously incremented on every anonymous GET with no dedupe, so
    it was trivially inflatable and also wrote to the database on every read
    (security/AUDIT.md SAHA-038). Sellers and buyers read this number as an
    interest signal, so it needs to mean something.

    Anonymous views are not counted at all: without an identity there is nothing
    to deduplicate on that an inflater could not simply rotate.
    """
    if viewer_id is None:
        return

    from app.ai.sessions import get_redis

    try:
        marker = f"listing:view:{listing_id}:{viewer_id}"
        if not await get_redis().set(marker, "1", ex=_VIEW_DEDUPE_TTL, nx=True):
            return  # already counted this viewer recently
    except Exception as exc:  # noqa: BLE001 — a metric must never break a read
        logger.warning("view_dedupe_unavailable", error=str(exc))
        return

    await db.execute(
        update(IPListing)
        .where(IPListing.id == listing_id)
        .values(view_count=IPListing.view_count + 1)
    )
    await db.commit()


async def get_public_listings(db: AsyncSession, limit: int = 20, offset: int = 0) -> list[IPListing]:
    result = await db.execute(
        select(IPListing)
        .options(selectinload(IPListing.bom_items), selectinload(IPListing.vault_assets))
        .where(IPListing.status == ListingStatus.PUBLISHED)
        .order_by(IPListing.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    return list(result.scalars().all())


async def send_dialogue_message(
    db: AsyncSession,
    listing: IPListing,
    user_id: uuid.UUID,
    user_message: str,
) -> str:
    history = await ai_sessions.get_messages(listing.id, user_id)

    if not history:
        # First message: prime with system prompt and AI greeting
        await ai_sessions.set_messages(listing.id, user_id, [])
        history = []

        if listing.status == ListingStatus.DRAFT:
            listing.status = ListingStatus.AI_GENERATING
            await db.commit()

    await ai_sessions.append_message(listing.id, user_id, "user", user_message)
    history.append({"role": "user", "content": user_message})

    messages = [Message(role="system", content=SYSTEM_PROMPT)] + [
        Message(role=m["role"], content=m["content"]) for m in history
    ]

    response = await llm.complete(
        messages=messages,
        function_name="bom_creator_dialogue",
        temperature=0.4,
        max_tokens=1000,
    )

    ai_reply = response.content
    await ai_sessions.append_message(listing.id, user_id, "assistant", ai_reply)
    return ai_reply


async def get_ai_greeting(db: AsyncSession, listing: IPListing, user_id: uuid.UUID) -> str:
    """Returns the initial AI greeting for a new session (no user message needed)."""
    history = await ai_sessions.get_messages(listing.id, user_id)
    if history:
        for m in history:
            if m["role"] == "assistant":
                return m["content"]
        return ""

    messages = [
        Message(role="system", content=SYSTEM_PROMPT),
        Message(role="user", content=f'My IP is called "{listing.title}". Please start the documentation process.'),
    ]

    response = await llm.complete(
        messages=messages,
        function_name="bom_creator_dialogue",
        temperature=0.5,
        max_tokens=500,
    )

    greeting = response.content
    await ai_sessions.set_messages(listing.id, user_id, [
        {"role": "user", "content": f'My IP is called "{listing.title}". Please start the documentation process.'},
        {"role": "assistant", "content": greeting},
    ])

    if listing.status == ListingStatus.DRAFT:
        listing.status = ListingStatus.AI_GENERATING
        await db.commit()

    return greeting


async def finalize_bom(
    db: AsyncSession,
    listing: IPListing,
    user_id: uuid.UUID,
) -> list[BOMItem]:
    """Ask the AI to output the structured BOM from the conversation, save to DB."""
    if listing.status not in (ListingStatus.DRAFT, ListingStatus.AI_GENERATING):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Listing cannot be finalized in its current status")

    history = await ai_sessions.get_messages(listing.id, user_id)
    if not history:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No dialogue session found. Start the AI dialogue first.")

    messages = [Message(role="system", content=SYSTEM_PROMPT)] + [
        Message(role=m["role"], content=m["content"]) for m in history
    ] + [Message(role="user", content=FINALIZE_PROMPT)]

    response = await llm.complete(
        messages=messages,
        function_name="bom_creator_dialogue",
        temperature=0.1,
        max_tokens=3000,
    )

    raw = response.content
    bom_data = _extract_json(raw)
    if not bom_data:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="AI could not produce a valid BOM. Continue the dialogue and try again.",
        )

    # Delete existing BOM items before replacing
    from sqlalchemy import delete
    await db.execute(delete(BOMItem).where(BOMItem.listing_id == listing.id))

    bom_items = []
    for item_data in bom_data.get("bom_items", []):
        item = BOMItem(
            listing_id=listing.id,
            material_name=item_data["material_name"],
            specification=item_data.get("specification"),
            quantity_per_unit=Decimal(str(item_data["quantity_per_unit"])),
            unit_of_measure=item_data["unit_of_measure"],
            shelf_life_days=item_data.get("shelf_life_days"),
            procurement_cadence=item_data.get("procurement_cadence"),
            is_critical=item_data.get("is_critical", False),
            notes=item_data.get("notes"),
        )
        db.add(item)
        bom_items.append(item)

    listing.public_description = bom_data.get("public_description") or listing.public_description
    listing.tags = bom_data.get("tags") or listing.tags or []
    listing.equipment_requirements = bom_data.get("equipment_requirements") or listing.equipment_requirements or []
    listing.batch_size_definition = bom_data.get("batch_size_definition") or listing.batch_size_definition
    listing.status = ListingStatus.REVIEW

    await db.commit()
    await db.refresh(listing)
    for item in bom_items:
        await db.refresh(item)

    return bom_items


async def publish_listing(
    db: AsyncSession,
    listing: IPListing,
    public_description: str | None = None,
) -> IPListing:
    if listing.status != ListingStatus.REVIEW:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Listing must be in 'review' status to publish. Current: {listing.status.value}",
        )

    if public_description:
        listing.public_description = public_description

    if not listing.public_description:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="public_description is required before publishing")

    point_id = uuid.uuid4()
    try:
        await embeddings.index_listing(
            listing_id=listing.id,
            point_id=point_id,
            title=listing.title,
            public_description=listing.public_description,
            tags=listing.tags or [],
            product_category=listing.product_category,
            creator_id=listing.creator_id,
        )
        listing.qdrant_point_id = point_id
    except Exception as e:
        logger.warning("qdrant_index_failed", listing_id=str(listing.id), error=str(e))

    listing.status = ListingStatus.PUBLISHED
    await db.commit()
    await db.refresh(listing)

    from app.core import metrics
    metrics.listings_published_total.inc()

    return listing


async def add_vault_asset(db: AsyncSession, asset: IPVaultAsset) -> IPVaultAsset:
    db.add(asset)
    await db.commit()
    await db.refresh(asset)
    return asset


def _extract_json(text: str) -> dict | None:
    match = re.search(r"```json\s*([\s\S]+?)\s*```", text)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            pass
    try:
        return json.loads(text.strip())
    except json.JSONDecodeError:
        return None
