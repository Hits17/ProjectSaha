import uuid
from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.ratelimit import WRITE_LIMIT, limiter
from app.core.security import get_current_user, require_collaborator
from app.db.models.open_resource import OpenResource, OpenResourceStatus
from app.db.models.research import ResearchCollection, ResearchCollectionItem, SavedResearchSearch
from app.db.models.user import User
from app.db.session import get_db

router = APIRouter(prefix="/api/v1/research", tags=["private-research"])


class CollectionCreate(BaseModel):
    model_config = {"str_strip_whitespace": True}
    name: str = Field(min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=2000)


class CollectionResponse(BaseModel):
    id: uuid.UUID
    name: str
    description: str | None
    created_at: datetime
    model_config = {"from_attributes": True}


class ItemNote(BaseModel):
    note: str | None = Field(default=None, max_length=3000)


class ItemResponse(BaseModel):
    resource_id: uuid.UUID
    resource_title: str | None
    source_url: str | None
    note: str | None
    created_at: datetime


class SearchCreate(BaseModel):
    model_config = {"str_strip_whitespace": True}
    label: str = Field(min_length=1, max_length=120)
    query: str = Field(min_length=1, max_length=255)
    resource_type: Literal["", "patent", "research_paper", "trademark"] = ""


class SearchResponse(SearchCreate):
    id: uuid.UUID
    created_at: datetime
    model_config = {"from_attributes": True, "str_strip_whitespace": True}


async def owned_collection(db: AsyncSession, collection_id: uuid.UUID, actor: User, *, lock: bool = False) -> ResearchCollection:
    stmt = select(ResearchCollection).where(ResearchCollection.id == collection_id, ResearchCollection.owner_id == actor.id)
    collection = await db.scalar(stmt.with_for_update() if lock else stmt)
    if collection is None:
        raise HTTPException(status_code=404, detail="Collection not found")
    return collection


@router.get("/collections", response_model=list[CollectionResponse])
async def collections(
    offset: int = Query(default=0, ge=0, le=10000), db: AsyncSession = Depends(get_db), actor: User = Depends(get_current_user),
):
    return list((await db.execute(select(ResearchCollection).where(ResearchCollection.owner_id == actor.id).order_by(ResearchCollection.created_at.desc(), ResearchCollection.id).limit(50).offset(offset))).scalars().all())


@router.post("/collections", response_model=CollectionResponse, status_code=201)
@limiter.limit(WRITE_LIMIT)
async def create_collection(body: CollectionCreate, request: Request, db: AsyncSession = Depends(get_db), actor: User = Depends(require_collaborator)):
    await db.execute(select(User.id).where(User.id == actor.id).with_for_update())
    if (await db.scalar(select(func.count()).select_from(ResearchCollection).where(ResearchCollection.owner_id == actor.id))) >= 100:
        raise HTTPException(status_code=409, detail="You can keep up to 100 research collections.")
    collection = ResearchCollection(owner_id=actor.id, **body.model_dump())
    db.add(collection)
    await db.commit()
    await db.refresh(collection)
    return collection


@router.delete("/collections/{collection_id}", status_code=204)
async def delete_collection(collection_id: uuid.UUID, db: AsyncSession = Depends(get_db), actor: User = Depends(get_current_user)):
    collection = await owned_collection(db, collection_id, actor)
    await db.delete(collection)
    await db.commit()


@router.get("/collections/{collection_id}/items", response_model=list[ItemResponse])
async def items(
    collection_id: uuid.UUID, offset: int = Query(default=0, ge=0, le=10000),
    db: AsyncSession = Depends(get_db), actor: User = Depends(get_current_user),
):
    await owned_collection(db, collection_id, actor)
    rows = (await db.execute(select(ResearchCollectionItem, OpenResource).join(OpenResource, OpenResource.id == ResearchCollectionItem.resource_id).where(ResearchCollectionItem.collection_id == collection_id).order_by(ResearchCollectionItem.created_at.desc(), ResearchCollectionItem.id).limit(50).offset(offset))).all()
    result = []
    for item, source in rows:
        visible = source.is_active and source.status == OpenResourceStatus.APPROVED
        result.append(ItemResponse(resource_id=item.resource_id, resource_title=source.title if visible else None,
            source_url=source.source_url if visible else None, note=item.note, created_at=item.created_at))
    return result


@router.put("/collections/{collection_id}/items/{resource_id}", status_code=204)
@limiter.limit(WRITE_LIMIT)
async def save_item(
    collection_id: uuid.UUID, resource_id: uuid.UUID, body: ItemNote, request: Request,
    db: AsyncSession = Depends(get_db), actor: User = Depends(require_collaborator),
):
    await owned_collection(db, collection_id, actor, lock=True)
    existing = await db.scalar(select(ResearchCollectionItem.id).where(ResearchCollectionItem.collection_id == collection_id, ResearchCollectionItem.resource_id == resource_id))
    source = await db.get(OpenResource, resource_id)
    if source is None or (existing is None and (not source.is_active or source.status != OpenResourceStatus.APPROVED)):
        raise HTTPException(status_code=404, detail="Resource not found")
    if existing is None and (await db.scalar(select(func.count()).select_from(ResearchCollectionItem).where(ResearchCollectionItem.collection_id == collection_id))) >= 1000:
        raise HTTPException(status_code=409, detail="A collection can contain up to 1,000 resources.")
    stmt = insert(ResearchCollectionItem).values(id=uuid.uuid4(), collection_id=collection_id, resource_id=resource_id, note=body.note)
    if "note" in body.model_fields_set:
        stmt = stmt.on_conflict_do_update(constraint="uq_collection_resource", set_={"note": body.note})
    else:
        stmt = stmt.on_conflict_do_nothing(constraint="uq_collection_resource")
    await db.execute(stmt)
    await db.commit()


@router.delete("/collections/{collection_id}/items/{resource_id}", status_code=204)
async def remove_item(collection_id: uuid.UUID, resource_id: uuid.UUID, db: AsyncSession = Depends(get_db), actor: User = Depends(get_current_user)):
    from sqlalchemy import delete
    await owned_collection(db, collection_id, actor)
    await db.execute(delete(ResearchCollectionItem).where(ResearchCollectionItem.collection_id == collection_id, ResearchCollectionItem.resource_id == resource_id))
    await db.commit()


@router.get("/searches", response_model=list[SearchResponse])
async def searches(offset: int = Query(default=0, ge=0, le=10000), db: AsyncSession = Depends(get_db), actor: User = Depends(get_current_user)):
    return list((await db.execute(select(SavedResearchSearch).where(SavedResearchSearch.owner_id == actor.id).order_by(SavedResearchSearch.created_at.desc(), SavedResearchSearch.id).limit(50).offset(offset))).scalars().all())


@router.post("/searches", status_code=204)
@limiter.limit(WRITE_LIMIT)
async def save_search(body: SearchCreate, request: Request, db: AsyncSession = Depends(get_db), actor: User = Depends(require_collaborator)):
    await db.execute(select(User.id).where(User.id == actor.id).with_for_update())
    existing = await db.scalar(select(SavedResearchSearch.id).where(SavedResearchSearch.owner_id == actor.id, SavedResearchSearch.query == body.query, SavedResearchSearch.resource_type == body.resource_type))
    if existing is None and (await db.scalar(select(func.count()).select_from(SavedResearchSearch).where(SavedResearchSearch.owner_id == actor.id))) >= 100:
        raise HTTPException(status_code=409, detail="You can keep up to 100 saved searches.")
    await db.execute(insert(SavedResearchSearch).values(id=uuid.uuid4(), owner_id=actor.id, **body.model_dump())
        .on_conflict_do_update(constraint="uq_owner_research_search", set_={"label": body.label}))
    await db.commit()


@router.delete("/searches/{search_id}", status_code=204)
async def remove_search(search_id: uuid.UUID, db: AsyncSession = Depends(get_db), actor: User = Depends(get_current_user)):
    from sqlalchemy import delete
    await db.execute(delete(SavedResearchSearch).where(SavedResearchSearch.id == search_id, SavedResearchSearch.owner_id == actor.id))
    await db.commit()
