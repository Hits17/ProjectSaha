import uuid
from typing import Literal

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from pydantic import BaseModel, Field, SecretStr
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import write_audit_log
from app.core.ratelimit import AUTH_LIMIT, WRITE_LIMIT, limiter
from app.core.security import get_current_user, require_collaborator, validate_step_up_token
from app.db.models.chat import ChatIdentity
from app.db.models.user import User
from app.db.session import get_db
from app.integrations import matrix
from app.services import chat

router = APIRouter(prefix="/api/v1/chat", tags=["encrypted-chat"])


async def require_chat_link_auth(request: Request, actor: User = Depends(require_collaborator)):
    # Reuse token verification with a collaboration user explicitly supplied:
    # financial KYC is not required, but a stolen bearer alone cannot link an
    # attacker's Matrix identity to the victim's Saha memberships.
    return validate_step_up_token(request, actor)


class LinkIdentity(BaseModel):
    # Used only for whoami against a fixed homeserver. Never stored or logged.
    access_token: SecretStr = Field(min_length=10, max_length=4096)


class ChatStatus(BaseModel):
    configured: bool
    matrix_user_id: str | None
    client_url: str | None
    homeserver_url: str | None


class ChatRoomResponse(BaseModel):
    room_id: str
    url: str
    transport: Literal["matrix"]
    end_to_end_encrypted: bool


@router.get("/status", response_model=ChatStatus)
async def status(db: AsyncSession = Depends(get_db), actor: User = Depends(get_current_user)):
    identity = await db.get(ChatIdentity, actor.id)
    ready = matrix.configured()
    return ChatStatus(configured=ready, matrix_user_id=identity.matrix_user_id if identity else None,
                      client_url=matrix.settings.ELEMENT_WEB_URL if ready else None,
                      homeserver_url=matrix.settings.MATRIX_HOMESERVER_URL if ready else None)


@router.post("/identity", response_model=ChatStatus)
@limiter.limit(AUTH_LIMIT)
async def link(
    body: LinkIdentity, request: Request, background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db), actor: User = Depends(require_chat_link_auth),
):
    matrix_id = await matrix.verify_identity(body.access_token.get_secret_value())
    existing = await db.get(ChatIdentity, actor.id)
    if existing and existing.matrix_user_id != matrix_id:
        raise HTTPException(status_code=409, detail="A different chat account is already linked. Contact support for a reviewed migration; old room access must be revoked first.")
    if not existing:
        db.add(ChatIdentity(user_id=actor.id, matrix_user_id=matrix_id))
        try:
            await db.commit()
        except IntegrityError:
            await db.rollback()
            raise HTTPException(status_code=409, detail="This chat account is already linked.") from None
    background_tasks.add_task(write_audit_log, action="chat.identity_linked", user_id=actor.id, resource_type="user", resource_id=actor.id)
    return await status(db, actor)


@router.post("/rooms/{scope}/{scope_id}", response_model=ChatRoomResponse)
@limiter.limit(WRITE_LIMIT)
async def open_room(
    scope: Literal["community", "proposal", "transaction"], scope_id: uuid.UUID,
    request: Request, background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db), actor: User = Depends(require_collaborator),
):
    result = await chat.open_room(db, scope, scope_id, actor)
    background_tasks.add_task(write_audit_log, action="chat.opened", user_id=actor.id, resource_type=scope, resource_id=scope_id)
    return result
