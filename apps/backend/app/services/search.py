"""
Discovery search service.
Flow: parse intent → embed refined query → Qdrant ANN search → fetch full listings → save demand signal.
"""

import json
import uuid

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.ai.client import Message, llm
from app.api.schemas.search import ParsedIntent
from app.db.models.listing import IPListing, ListingStatus
from app.services.embeddings import embed_text

logger = structlog.get_logger()

_INTENT_SYSTEM = """You are a search intent parser for an IP marketplace.
Given a natural language query from a manufacturer or buyer, extract structured intent.

Output ONLY valid JSON in this exact format:
{
  "product_type": "short product type or null",
  "industry": "industry vertical or null",
  "keywords": ["keyword1", "keyword2"],
  "refined_query": "a clean, specific query optimized for semantic search"
}

Rules:
- refined_query must always be present and should be the most semantically rich version of the user's intent
- Keep keywords to 3-5 most important terms
- Be specific: "biodegradable wound dressing" not "medical product"
"""


async def parse_intent(query: str) -> ParsedIntent:
    try:
        response = await llm.complete(
            messages=[
                Message(role="system", content=_INTENT_SYSTEM),
                Message(role="user", content=query),
            ],
            function_name="discovery_intent_parse",
            temperature=0.1,
            max_tokens=300,
        )
        raw = response.content.strip()
        # Strip markdown fences if present
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        data = json.loads(raw)
        return ParsedIntent(
            product_type=data.get("product_type"),
            industry=data.get("industry"),
            keywords=data.get("keywords", []),
            refined_query=data.get("refined_query", query),
        )
    except Exception as e:
        logger.warning("intent_parse_failed", error=str(e), query=query)
        return ParsedIntent(refined_query=query, keywords=[])


async def semantic_search(
    db: AsyncSession,
    query: str,
    limit: int = 10,
    user_id: uuid.UUID | None = None,
) -> tuple[ParsedIntent, list[tuple[IPListing, float]]]:
    intent = await parse_intent(query)

    embedding = await embed_text(intent.refined_query, input_type="query")

    from app.integrations.vector import search_vectors
    hits = await search_vectors(embedding, limit=limit)

    if not hits:
        return intent, []

    listing_ids = []
    score_map: dict[str, float] = {}
    for hit in hits:
        lid = hit.payload.get("listing_id")
        if lid:
            listing_ids.append(uuid.UUID(lid))
            score_map[lid] = hit.score

    if not listing_ids:
        return intent, []

    result = await db.execute(
        select(IPListing)
        .options(selectinload(IPListing.bom_items), selectinload(IPListing.vault_assets))
        .where(IPListing.id.in_(listing_ids))
        .where(IPListing.status == ListingStatus.PUBLISHED)
    )
    listings = result.scalars().all()

    # Preserve Qdrant ranking order
    listings_by_id = {str(l.id): l for l in listings}
    ordered = [
        (listings_by_id[str(lid)], score_map[str(lid)])
        for lid in listing_ids
        if str(lid) in listings_by_id
    ]

    # Persist demand signal as background work (best-effort)
    try:
        await _save_demand_signal(db, query, intent, len(ordered), user_id)
    except Exception as e:
        logger.warning("demand_signal_save_failed", error=str(e))

    from app.core import metrics
    metrics.searches_total.inc()
    if len(ordered) == 0:
        metrics.search_zero_results_total.inc()

    return intent, ordered


async def _save_demand_signal(
    db: AsyncSession,
    query_text: str,
    intent: ParsedIntent,
    result_count: int,
    user_id: uuid.UUID | None,
) -> None:
    from sqlalchemy import text
    await db.execute(
        text(
            "INSERT INTO demand_signals (id, query_text, parsed_intent, result_count, user_id) "
            "VALUES (:id, :query_text, CAST(:parsed_intent AS JSONB), :result_count, :user_id)"
        ),
        {
            "id": str(uuid.uuid4()),
            "query_text": query_text,
            "parsed_intent": json.dumps(intent.model_dump()),
            "result_count": result_count,
            "user_id": str(user_id) if user_id else None,
        },
    )
    await db.commit()
