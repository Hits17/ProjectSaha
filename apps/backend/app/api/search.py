from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas.listing import PublicListingResponse
from app.api.schemas.open_resource import OpenResourceResponse
from app.api.schemas.search import SearchRequest, SearchResponse, SearchResult
from app.core.ratelimit import limiter
from app.core.security import get_optional_user
from app.db.session import get_db
from app.services import open_resources as resource_svc
from app.services.search import semantic_search

router = APIRouter(prefix="/api/v1/search", tags=["discovery"])

# Below this many listing hits, a search counts as unmet demand and we offer
# open-library resources the searcher could build the thing from instead.
_SPARSE_RESULTS_THRESHOLD = 3


@router.post("", response_model=SearchResponse)
@limiter.limit("30/minute")
async def search_listings(
    body: SearchRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_optional_user),
):
    user_id = current_user.id if current_user else None
    intent, pairs = await semantic_search(db, body.query, limit=body.limit, user_id=user_id)

    results = [
        SearchResult(listing=PublicListingResponse.model_validate(listing), score=round(score, 4))
        for listing, score in pairs
    ]

    suggestions: list[OpenResourceResponse] = []
    if len(results) < _SPARSE_RESULTS_THRESHOLD:
        terms = [*intent.keywords, intent.product_type, intent.industry]
        suggestions = [
            OpenResourceResponse.model_validate(r)
            for r in await resource_svc.suggest_for_terms(db, terms)
        ]

    return SearchResponse(
        intent=intent,
        results=results,
        total=len(results),
        open_resource_suggestions=suggestions,
    )
