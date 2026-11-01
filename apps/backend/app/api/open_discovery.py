from urllib.parse import urlencode

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas.open_resource import OpenResourceResponse
from app.core.ratelimit import ANON_READ_LIMIT, limiter
from app.core.security import get_optional_user
from app.db.models.open_resource import OpenResourceType
from app.db.models.user import User
from app.db.session import get_db
from app.services import open_resources

router = APIRouter(prefix="/api/v1/open-discovery", tags=["open-discovery"])


class DiscoverySource(BaseModel):
    name: str
    url: str
    description: str


class DiscoveryResponse(BaseModel):
    query: str
    resources: list[OpenResourceResponse]
    sources: list[DiscoverySource]
    has_more: bool
    offset: int
    coverage: str = "Saha's curated library plus links to independent patent search services. External search results are not imported or certified by Saha."


def source_links(query: str) -> list[DiscoverySource]:
    return [
        DiscoverySource(name="Google Patents", url="https://patents.google.com/?" + urlencode({"q": query}), description="Search patent publications across multiple patent offices."),
        DiscoverySource(name="Espacenet", url="https://worldwide.espacenet.com/patent/search?" + urlencode({"q": query}), description="Search EPO's worldwide patent database and inspect legal-event information."),
        DiscoverySource(name="WIPO PATENTSCOPE", url="https://patentscope.wipo.int/search/en/search.jsf", description="Open WIPO's search to explore international patent publications."),
    ]


@router.get("", response_model=DiscoveryResponse)
@limiter.limit(ANON_READ_LIMIT)
async def discover(
    request: Request, q: str = Query(default="", max_length=255),
    resource_type: OpenResourceType | None = None,
    category: str | None = Query(default=None, max_length=100),
    offset: int = Query(default=0, ge=0, le=10000), limit: int = Query(default=24, ge=1, le=50),
    db: AsyncSession = Depends(get_db), viewer: User | None = Depends(get_optional_user),
):
    rows = await open_resources.browse(db, q=q.strip() or None, resource_type=resource_type,
        category=category, limit=limit + 1, offset=offset, user_id=viewer.id if viewer else None)
    return DiscoveryResponse(query=q.strip(), resources=[OpenResourceResponse.model_validate(r) for r in rows[:limit]],
                             sources=source_links(q.strip()), has_more=len(rows) > limit, offset=offset)
