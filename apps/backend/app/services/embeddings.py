"""
Embedding service using NVIDIA NV-EmbedQA-E5-v5 (1024 dims).
Upserts listing vectors into Qdrant for semantic search in Sprint 4.
"""

import uuid

import httpx

from app.core.config import settings
from app.integrations import vector

EMBED_MODEL = "nvidia/nv-embedqa-e5-v5"
_EMBED_URL = "https://integrate.api.nvidia.com/v1/embeddings"


async def embed_text(text: str, input_type: str = "passage") -> list[float]:
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(
            _EMBED_URL,
            headers={
                "Authorization": f"Bearer {settings.NVIDIA_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "input": [text],
                "model": EMBED_MODEL,
                "input_type": input_type,
                "truncate": "END",
            },
        )
        resp.raise_for_status()
        data = resp.json()
    return data["data"][0]["embedding"]


async def index_listing(
    listing_id: uuid.UUID,
    point_id: uuid.UUID,
    title: str,
    public_description: str,
    tags: list[str],
    product_category: str | None,
    creator_id: uuid.UUID,
) -> None:
    embed_text_input = f"{title}. {public_description}."
    if tags:
        embed_text_input += f" Tags: {', '.join(tags)}."
    if product_category:
        embed_text_input += f" Category: {product_category}."

    embedding = await embed_text(embed_text_input)

    await vector.upsert_vectors([
        {
            "id": str(point_id),
            "vector": embedding,
            "payload": {
                "listing_id": str(listing_id),
                "creator_id": str(creator_id),
                "title": title,
                "public_description": public_description,
                "tags": tags,
                "product_category": product_category,
            },
        }
    ])


async def remove_listing(point_id: uuid.UUID) -> None:
    from qdrant_client.models import PointIdsList
    client = vector.get_qdrant()
    await client.delete(
        collection_name=settings.QDRANT_COLLECTION,
        points_selector=PointIdsList(points=[str(point_id)]),
    )
