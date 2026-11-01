"""Retired server-decrypted proposal transport. New chat uses Matrix E2EE.

Historical ciphertext stays in the database for the existing retention policy;
this service neither decrypts it nor accepts new plaintext. Contact detection
cannot run server-side on E2EE messages. Public posts retain moderation.
"""
import uuid
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.models.proposal import Proposal

async def send_message(db: AsyncSession, proposal: Proposal, sender_id: uuid.UUID, plaintext: str) -> dict:
    raise HTTPException(status_code=410, detail="Server-decrypted chat is retired. Open the end-to-end encrypted chat workspace.")

async def get_messages(db: AsyncSession, proposal: Proposal, requesting_user_id: uuid.UUID) -> list[dict]:
    raise HTTPException(status_code=410, detail="Legacy messages were not end-to-end encrypted. Open the encrypted chat workspace; legacy records are retained separately.")
