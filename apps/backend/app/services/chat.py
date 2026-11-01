import uuid

from fastapi import HTTPException
from sqlalchemy import and_, or_, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.chat import ChatIdentity, EncryptedChatRoom
from app.db.models.community import CommunityMembership
from app.db.models.proposal import Proposal
from app.db.models.transaction import Transaction
from app.db.models.user import User
from app.integrations import matrix


async def scope_lock(db: AsyncSession, scope: str, scope_id: uuid.UUID) -> None:
    # Same lock order for open, removal and account deactivation. Only room
    # administration is serialized; encrypted message traffic bypasses Saha.
    await db.execute(text("SELECT pg_advisory_xact_lock(hashtext('saha.chat.membership'))"))
    await db.execute(text("SELECT pg_advisory_xact_lock(hashtext(:key))"), {"key": f"saha.chat:{scope}:{scope_id}"})


async def participants(db: AsyncSession, scope: str, scope_id: uuid.UUID, actor: User) -> list[uuid.UUID]:
    if scope == "community":
        members = list((await db.execute(select(CommunityMembership.user_id).join(User, User.id == CommunityMembership.user_id).where(CommunityMembership.community_id == scope_id, User.is_active.is_(True)))).scalars().all())
        if actor.id not in members:
            raise HTTPException(status_code=403, detail="Join this space to use its encrypted chat.")
        return members
    model = {"proposal": Proposal, "transaction": Transaction}.get(scope)
    if model is None:
        raise HTTPException(status_code=422, detail="Unknown chat scope")
    record = await db.get(model, scope_id)
    if not record or actor.id not in (record.buyer_id, record.seller_id):
        raise HTTPException(status_code=404, detail="Conversation not found")
    return [record.buyer_id, record.seller_id]


async def open_room(db: AsyncSession, scope: str, scope_id: uuid.UUID, actor: User) -> dict:
    matrix.require_configuration()
    await scope_lock(db, scope, scope_id)
    member_ids = await participants(db, scope, scope_id, actor)
    identities = list((await db.execute(select(ChatIdentity).join(User, User.id == ChatIdentity.user_id).where(ChatIdentity.user_id.in_(member_ids), User.is_active.is_(True)))).scalars().all())
    if not any(i.user_id == actor.id for i in identities):
        raise HTTPException(status_code=409, detail="Link your personal Matrix account before opening encrypted chat.")
    await matrix.assert_keyless_service_account()
    record = await db.scalar(select(EncryptedChatRoom).where(EncryptedChatRoom.scope == scope, EncryptedChatRoom.scope_id == scope_id))
    if record is None:
        room_id = await matrix.ensure_room(scope, str(scope_id))
        record = EncryptedChatRoom(scope=scope, scope_id=scope_id, matrix_room_id=room_id)
        db.add(record)
    await matrix.reconcile(record.matrix_room_id, scope, str(scope_id), {i.matrix_user_id for i in identities})
    await db.commit()
    return {"room_id": record.matrix_room_id, "url": matrix.element_url(record.matrix_room_id), "transport": "matrix", "end_to_end_encrypted": True}


async def revoke_space_member(db: AsyncSession, community_id: uuid.UUID, user_id: uuid.UUID) -> None:
    """Fail closed: don't confirm removal while an existing Matrix grant survives."""
    await scope_lock(db, "community", community_id)
    room = await db.scalar(select(EncryptedChatRoom).where(EncryptedChatRoom.scope == "community", EncryptedChatRoom.scope_id == community_id))
    identity = await db.get(ChatIdentity, user_id)
    if room and identity:
        from urllib.parse import quote
        events = await matrix.inspect_room(room.matrix_room_id, "community", str(community_id))
        if any(e.get("type") == "m.room.member" and e.get("state_key") == identity.matrix_user_id
               and e.get("content", {}).get("membership") in ("join", "invite") for e in events):
            await matrix.call("POST", "rooms/" + quote(room.matrix_room_id, safe="") + "/kick", body={"user_id": identity.matrix_user_id, "reason": "Saha membership ended"})


async def revoke_user(db: AsyncSession, user_id: uuid.UUID) -> None:
    """Disable access in existing external rooms before confirming deactivation."""
    from urllib.parse import quote
    identity = await db.get(ChatIdentity, user_id)
    if identity is None:
        return
    await scope_lock(db, "account", user_id)
    # Lock the user so an in-flight room opener cannot invite after revocation.
    await db.execute(select(User).where(User.id == user_id).with_for_update())
    community_ids = select(CommunityMembership.community_id).where(CommunityMembership.user_id == user_id)
    proposal_ids = select(Proposal.id).where(or_(Proposal.buyer_id == user_id, Proposal.seller_id == user_id))
    transaction_ids = select(Transaction.id).where(or_(Transaction.buyer_id == user_id, Transaction.seller_id == user_id))
    relevant = or_(
        and_(EncryptedChatRoom.scope == "community", EncryptedChatRoom.scope_id.in_(community_ids)),
        and_(EncryptedChatRoom.scope == "proposal", EncryptedChatRoom.scope_id.in_(proposal_ids)),
        and_(EncryptedChatRoom.scope == "transaction", EncryptedChatRoom.scope_id.in_(transaction_ids)),
    )
    rooms = list((await db.execute(select(EncryptedChatRoom).where(relevant).order_by(EncryptedChatRoom.scope, EncryptedChatRoom.scope_id))).scalars().all())
    for room in rooms:
        await scope_lock(db, room.scope, room.scope_id)
        events = await matrix.inspect_room(room.matrix_room_id, room.scope, str(room.scope_id))
        if any(e.get("type") == "m.room.member" and e.get("state_key") == identity.matrix_user_id
               and e.get("content", {}).get("membership") in ("join", "invite") for e in events):
            await matrix.call("POST", "rooms/" + quote(room.matrix_room_id, safe="") + "/kick", body={"user_id": identity.matrix_user_id, "reason": "Saha account deactivated"})
