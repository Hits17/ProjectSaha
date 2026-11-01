"""Bounded media, mention identity and reaction aggregation for the social feed."""
import re
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, UploadFile
from sqlalchemy import delete, func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.models.social_media import PostMedia, PostReaction
from app.db.models.social import Post, UserProfile
from app.db.models.user import User
from app.integrations import storage

IMAGE_LIMIT = 8 * 1024 * 1024
VIDEO_LIMIT = 40 * 1024 * 1024
DRAFT_LIMIT = 128 * 1024 * 1024
MENTION = re.compile(r"@\[([^\]\n]{1,255})\]\(([0-9a-fA-F-]{36})\)")
REACTIONS = {"like", "celebrate", "support", "love", "insightful", "curious"}


def detect_media(data: bytes, declared: str) -> str:
    kind = None
    if data.startswith(b"\xff\xd8\xff"): kind = "image/jpeg"
    elif data.startswith(b"\x89PNG\r\n\x1a\n"): kind = "image/png"
    elif data[:4] == b"RIFF" and data[8:12] == b"WEBP": kind = "image/webp"
    elif len(data) >= 16 and data[4:8] == b"ftyp" and data[8:12] in {b"isom", b"iso2", b"mp41", b"mp42", b"avc1", b"M4V ", b"MSNV"}: kind = "video/mp4"
    elif data.startswith(b"\x1a\x45\xdf\xa3") and b"webm" in data[:4096]: kind = "video/webm"
    if not kind or declared.split(";")[0].lower().strip() != kind:
        raise HTTPException(415, "Use a JPEG, PNG, WebP image or MP4/WebM video matching its file type.")
    if not data or len(data) > (IMAGE_LIMIT if kind.startswith("image/") else VIDEO_LIMIT):
        raise HTTPException(413, "Images may be up to 8 MB; videos up to 40 MB.")
    return kind


async def read_media(file: UploadFile) -> tuple[bytes, str]:
    limit = IMAGE_LIMIT if (file.content_type or "").startswith("image/") else VIDEO_LIMIT
    data = bytearray()
    while True:
        part = await file.read(min(64 * 1024, limit + 1 - len(data)))
        if not part: break
        data.extend(part)
        if len(data) > limit: raise HTTPException(413, "Images may be up to 8 MB; videos up to 40 MB.")
    return bytes(data), detect_media(bytes(data), file.content_type or "")


def media_response(row: PostMedia) -> dict:
    return dict(id=row.id, content_type=row.content_type, byte_size=row.byte_size,
                alt_text=row.alt_text, position=row.position,
                url=f"/api/v1/social/media/{row.id}")


async def upload(db: AsyncSession, user: User, file: UploadFile, alt_text: str) -> PostMedia:
    data, content_type = await read_media(file)
    # Serialize draft quotas and attachment finalization for one owner.
    await db.execute(select(User.id).where(User.id == user.id).with_for_update())
    pending = list((await db.execute(select(PostMedia).where(PostMedia.owner_id == user.id, PostMedia.post_id.is_(None)))).scalars())
    cutoff = datetime.now(timezone.utc) - timedelta(days=1)
    for row in list(pending):
        if row.created_at < cutoff:
            await storage.delete_file(row.storage_key)
            await db.delete(row)
            pending.remove(row)
    if len(pending) >= 12 or sum(row.byte_size for row in pending) + len(data) > DRAFT_LIMIT:
        raise HTTPException(409, "Remove unused draft attachments before uploading more media.")
    row = PostMedia(id=uuid.uuid4(), owner_id=user.id, content_type=content_type,
                    byte_size=len(data), alt_text=alt_text.strip(), position=0)
    row.storage_key = f"social/{user.id}/{row.id}"
    await storage.upload_file(row.storage_key, data, content_type)
    try:
        db.add(row)
        await db.commit()
        await db.refresh(row)
    except Exception:
        await db.rollback()
        await storage.delete_file(row.storage_key)
        raise
    return row


async def attach(db: AsyncSession, author: User, post: Post, ids: list[uuid.UUID]) -> None:
    if not ids: return
    if len(ids) > 6 or len(set(ids)) != len(ids): raise HTTPException(422, "Choose up to six distinct attachments.")
    await db.execute(select(User.id).where(User.id == author.id).with_for_update())
    rows = list((await db.execute(select(PostMedia).where(PostMedia.id.in_(ids)).with_for_update())).scalars())
    if len(rows) != len(ids) or any(r.owner_id != author.id or r.post_id is not None for r in rows):
        raise HTTPException(403, "Only your unused uploads can be attached to this post.")
    if sum(r.content_type.startswith("video/") for r in rows) > 1:
        raise HTTPException(422, "Attach at most one video per post.")
    for row in rows:
        row.post_id = post.id
        row.position = ids.index(row.id)


async def assert_media_access(db: AsyncSession, media: PostMedia, viewer: User | None) -> None:
    from app.services.posts import assert_can_view
    if media.post_id is None:
        if viewer is None or viewer.id != media.owner_id:
            raise HTTPException(404, "Media not found")
        return
    post = await db.get(Post, media.post_id)
    if post is None: raise HTTPException(404, "Media not found")
    if viewer is not None and viewer.role == "admin" and viewer.id != post.author_id:
        from app.core.security import require_admin
        await require_admin(viewer)
        if post.deleted_at is not None:
            raise HTTPException(404, "Media not found")
        return
    await assert_can_view(db, post, viewer)


async def normalize_mentions(db: AsyncSession, body: str) -> str:
    matches = list(MENTION.finditer(body))
    if not matches: return body
    try: ids = {uuid.UUID(m[2]) for m in matches}
    except ValueError: raise HTTPException(422, "Invalid member mention")
    if len(ids) > 10: raise HTTPException(422, "Mention up to ten members per post or comment.")
    users = list((await db.execute(select(User).where(User.id.in_(ids), User.is_active.is_(True)))).scalars())
    names = {str(u.id): u.full_name.replace("]", "").replace("\n", " ")[:255] for u in users}
    if len(names) != len(ids): raise HTTPException(422, "A mentioned member is no longer available.")
    return MENTION.sub(lambda m: f"@[{names[str(uuid.UUID(m[2]))]}]({str(uuid.UUID(m[2]))})", body)


async def notify_mentions(post_id: uuid.UUID, actor_id: uuid.UUID, body: str) -> None:
    from app.db.session import AsyncSessionLocal
    from app.services.posts import assert_can_view, VISIBLE_STATUSES
    from app.services.notifications import notify_best_effort
    ids = {uuid.UUID(m[2]) for m in MENTION.finditer(body)} - {actor_id}
    if not ids: return
    async with AsyncSessionLocal() as db:
        post = await db.get(Post, post_id)
        if not post or post.deleted_at is not None or post.moderation_status not in VISIBLE_STATUSES: return
        for member in (await db.execute(select(User).where(User.id.in_(ids), User.is_active.is_(True)))).scalars():
            try: await assert_can_view(db, post, member)
            except HTTPException: continue
            # No post/space text is copied into a notification that may outlive membership.
            await notify_best_effort(member.id, "social.mention", "You were mentioned in a discussion", link=f"/dashboard/feed/{post.id}")


async def reaction_summary(db: AsyncSession, ids: list[uuid.UUID], viewer: User | None) -> tuple[dict, dict]:
    if not ids: return {}, {}
    counts = {}
    for pid, kind, count in (await db.execute(select(PostReaction.post_id, PostReaction.kind, func.count()).where(PostReaction.post_id.in_(ids)).group_by(PostReaction.post_id, PostReaction.kind))):
        counts.setdefault(pid, {})[kind] = count
    mine = dict((await db.execute(select(PostReaction.post_id, PostReaction.kind).where(PostReaction.post_id.in_(ids), PostReaction.user_id == viewer.id))).all()) if viewer else {}
    return counts, mine


async def react(db: AsyncSession, post: Post, user: User, kind: str | None) -> dict:
    from app.services.posts import assert_can_view
    await assert_can_view(db, post, user)
    if kind is not None and kind not in REACTIONS: raise HTTPException(422, "Unknown reaction")
    if kind is None:
        await db.execute(delete(PostReaction).where(PostReaction.post_id == post.id, PostReaction.user_id == user.id))
    else:
        await db.execute(insert(PostReaction).values(post_id=post.id, user_id=user.id, kind=kind).on_conflict_do_update(index_elements=["post_id", "user_id"], set_={"kind": kind}))
    await db.commit()
    counts, mine = await reaction_summary(db, [post.id], user)
    return {"reactions": counts.get(post.id, {}), "my_reaction": mine.get(post.id)}
