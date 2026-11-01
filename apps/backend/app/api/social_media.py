"""Authenticated media drafts; downloads always inherit the current post policy."""
import uuid
from typing import Literal
from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.config import settings
from app.core.ratelimit import ANON_READ_LIMIT, WRITE_LIMIT, limiter
from app.core.security import get_current_user, get_optional_user, require_collaborator
from app.db.models.social_media import PostMedia
from app.db.models.social import Post, UserProfile
from app.db.models.user import User
from app.db.session import get_db
from app.integrations import storage
from app.services import social_media as service

router = APIRouter(prefix="/api/v1/social", tags=["social-media"])


class ReactionRequest(BaseModel):
    kind: Literal["like", "celebrate", "support", "love", "insightful", "curious"] | None = None


@router.get("/members/search")
@limiter.limit(ANON_READ_LIMIT)
async def search_members(request: Request, q: str = Query(min_length=2, max_length=80),
                         db: AsyncSession = Depends(get_db), viewer: User = Depends(get_current_user)):
    # Public profile fields only. SQL wildcard characters are literal search input.
    term = q.strip().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    if len(term) < 2: return []
    rows = await db.execute(select(User.id, User.full_name, User.avatar_key, UserProfile.headline)
                            .outerjoin(UserProfile, UserProfile.user_id == User.id)
                            .where(User.is_active.is_(True), User.full_name.ilike(f"%{term}%", escape="\\"))
                            .order_by(User.full_name, User.id).limit(8))
    return [dict(user_id=r.id, full_name=r.full_name, has_avatar=bool(r.avatar_key), headline=r.headline) for r in rows]


@router.post("/media", status_code=201)
@limiter.limit(WRITE_LIMIT)
async def upload_media(request: Request, file: UploadFile = File(...), alt_text: str = Form(default="", max_length=500),
                       db: AsyncSession = Depends(get_db), user: User = Depends(require_collaborator)):
    return service.media_response(await service.upload(db, user, file, alt_text))


@router.get("/media/{media_id}")
@limiter.limit(ANON_READ_LIMIT)
async def get_media(media_id: uuid.UUID, request: Request, db: AsyncSession = Depends(get_db),
                    viewer: User | None = Depends(get_optional_user)):
    media = await db.get(PostMedia, media_id)
    if media is None: raise HTTPException(404, "Media not found")
    await service.assert_media_access(db, media, viewer)
    try:
        async with storage._s3_client() as s3:
            result = await s3.get_object(Bucket=settings.MINIO_BUCKET, Key=media.storage_key)
            async with result["Body"] as stream:
                data = await stream.read(media.byte_size + 1)
            if len(data) != media.byte_size: raise ValueError("Media size mismatch")
    except Exception as exc:
        raise HTTPException(503, "Media is temporarily unavailable") from exc
    return Response(data, media_type=media.content_type, headers={
        "Cache-Control": "private, no-store", "X-Content-Type-Options": "nosniff",
        "Content-Disposition": 'inline; filename="saha-media"',
        "Cross-Origin-Resource-Policy": "same-origin",
    })


@router.delete("/media/{media_id}", status_code=204)
async def remove_draft(media_id: uuid.UUID, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    await db.execute(select(User.id).where(User.id == user.id).with_for_update())
    media = await db.get(PostMedia, media_id, with_for_update=True)
    if media is None or media.owner_id != user.id: raise HTTPException(404, "Draft attachment not found")
    if media.post_id is not None: raise HTTPException(409, "Published attachments are part of their post. Delete the post to hide them.")
    await storage.delete_file(media.storage_key)
    await db.delete(media)
    await db.commit()


@router.put("/posts/{post_id}/reaction")
@limiter.limit(WRITE_LIMIT)
async def reaction(post_id: uuid.UUID, body: ReactionRequest, request: Request,
                   db: AsyncSession = Depends(get_db), user: User = Depends(require_collaborator)):
    post = await db.get(Post, post_id)
    if post is None: raise HTTPException(404, "Post not found")
    return await service.react(db, post, user, body.kind)
