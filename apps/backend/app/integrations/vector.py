"""
Qdrant vector store client.
Points to local Qdrant in dev; swap QDRANT_URL for Qdrant Cloud or Pinecone-compat in prod.
"""

from qdrant_client import AsyncQdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct, PointIdsList
from app.core.config import settings

EMBEDDING_DIM = 1024  # nvidia/nv-embedqa-e5-v5

_client: AsyncQdrantClient | None = None


def get_qdrant() -> AsyncQdrantClient:
    global _client
    if _client is None:
        _client = AsyncQdrantClient(url=settings.QDRANT_URL)
    return _client


async def ensure_collection_exists() -> None:
    client = get_qdrant()
    collections = await client.get_collections()
    names = [c.name for c in collections.collections]
    if settings.QDRANT_COLLECTION not in names:
        await client.create_collection(
            collection_name=settings.QDRANT_COLLECTION,
            vectors_config=VectorParams(size=EMBEDDING_DIM, distance=Distance.COSINE),
        )


async def upsert_vectors(points: list[dict]) -> None:
    client = get_qdrant()
    structs = [
        PointStruct(id=p["id"], vector=p["vector"], payload=p.get("payload", {}))
        for p in points
    ]
    await client.upsert(collection_name=settings.QDRANT_COLLECTION, points=structs)


async def search_vectors(query_vector: list[float], limit: int = 10, filters: dict | None = None):
    client = get_qdrant()
    response = await client.query_points(
        collection_name=settings.QDRANT_COLLECTION,
        query=query_vector,
        limit=limit,
        with_payload=True,
    )
    return response.points


async def ping() -> bool:
    try:
        client = get_qdrant()
        await client.get_collections()
        return True
    except Exception:
        return False
