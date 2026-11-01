from pydantic import BaseModel, Field
from app.api.schemas.listing import PublicListingResponse
from app.api.schemas.open_resource import OpenResourceResponse


class SearchRequest(BaseModel):
    query: str = Field(..., min_length=2, max_length=1000)
    limit: int = Field(10, ge=1, le=50)


class ParsedIntent(BaseModel):
    product_type: str | None = None
    industry: str | None = None
    keywords: list[str] = []
    refined_query: str


class SearchResult(BaseModel):
    # Teaser tier only. Search is reachable unauthenticated (get_optional_user),
    # so embedding the owner model here reproduced SAHA-003 through a second
    # route — the same leak, one endpoint over.
    listing: PublicListingResponse
    score: float


class SearchResponse(BaseModel):
    intent: ParsedIntent
    results: list[SearchResult]
    total: int
    # Demand-gap cross-link: when listings are scarce, open-library resources the
    # searcher could build the thing from ("no listings yet — build it yourself").
    open_resource_suggestions: list[OpenResourceResponse] = []
