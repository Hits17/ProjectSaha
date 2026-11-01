#!/usr/bin/env python
"""
Re-encrypt vault objects and negotiation messages under the current key version.

Why this exists: the vault key was found in production set to the placeholder
string committed in `.env.example` (security/AUDIT.md SAHA-001). Setting a new
key is not enough — every existing object is still wrapped under the old one, so
until they are re-wrapped the compromised key remains sufficient to read them.

Treat the old key as permanently compromised and every object encrypted under it
as having been stored in cleartext. Whether that requires user notification is
counsel's call, not this script's.

Usage
-----
    # dry run — reports what would change, touches nothing
    uv run python scripts/rotate_vault_key.py

    # apply
    uv run python scripts/rotate_vault_key.py --apply

Safety
------
* Idempotent: objects already at the target version are skipped.
* Per-object: a failure is logged and the run continues, so one unreadable
  object cannot strand the rest.
* Ordered: the database row is updated only after the re-encrypted object has
  been written, so a crash mid-run leaves a readable object with an accurate
  version marker — never the reverse.
* Reversible while V1 remains configured: the old key stays readable until you
  clear VAULT_ENCRYPTION_KEY, which should be the last step.
"""

import argparse
import asyncio
import sys

import structlog
from sqlalchemy import select

from app.db.models.listing import IPVaultAsset
from app.db.models.proposal import Message
from app.db.session import AsyncSessionLocal
from app.services import vault

logger = structlog.get_logger()


async def rotate_vault_assets(apply: bool) -> tuple[int, int, int]:
    done = skipped = failed = 0
    async with AsyncSessionLocal() as db:
        assets = (await db.execute(select(IPVaultAsset))).scalars().all()
        for asset in assets:
            current = asset.encryption_key_id or "v1"
            if current == vault.KEY_VERSION:
                skipped += 1
                continue
            if not apply:
                logger.info("would_rotate_asset", asset_id=str(asset.id), **{"from": current})
                done += 1
                continue
            try:
                plaintext = await vault.decrypt_file(asset.storage_key, current)
                await vault.reencrypt_object(asset.storage_key, current, vault.KEY_VERSION)
                asset.encryption_key_id = vault.KEY_VERSION
                if not asset.content_sha256:
                    asset.content_sha256 = vault.content_digest(plaintext)
                await db.commit()
                done += 1
                logger.info("rotated_asset", asset_id=str(asset.id))
            except Exception as exc:  # noqa: BLE001
                await db.rollback()
                failed += 1
                logger.error("asset_rotation_failed", asset_id=str(asset.id), error=str(exc))
    return done, skipped, failed


async def rotate_messages(apply: bool) -> tuple[int, int, int]:
    done = skipped = failed = 0
    async with AsyncSessionLocal() as db:
        messages = (await db.execute(select(Message))).scalars().all()
        for msg in messages:
            current = msg.encryption_key_id or "v1"
            if current == vault.KEY_VERSION:
                skipped += 1
                continue
            if not apply:
                done += 1
                continue
            try:
                plaintext = vault._decrypt(bytes(msg.encrypted_content), current)
                msg.encrypted_content = vault._encrypt(plaintext, vault.KEY_VERSION)
                msg.encryption_key_id = vault.KEY_VERSION
                await db.commit()
                done += 1
            except Exception as exc:  # noqa: BLE001
                await db.rollback()
                failed += 1
                logger.error("message_rotation_failed", message_id=str(msg.id), error=str(exc))
    return done, skipped, failed


async def main(apply: bool) -> int:
    from app.core.config import settings

    if not settings.VAULT_ENCRYPTION_KEY_V2:
        print("VAULT_ENCRYPTION_KEY_V2 is not set — nothing to rotate to.", file=sys.stderr)
        return 2

    mode = "APPLY" if apply else "DRY RUN"
    print(f"[{mode}] rotating to {vault.KEY_VERSION}\n")

    a_done, a_skip, a_fail = await rotate_vault_assets(apply)
    m_done, m_skip, m_fail = await rotate_messages(apply)

    print(f"vault assets : {a_done} rotated, {a_skip} already current, {a_fail} failed")
    print(f"messages     : {m_done} rotated, {m_skip} already current, {m_fail} failed")

    if not apply:
        print("\nDry run — nothing changed. Re-run with --apply.")
    elif a_fail or m_fail:
        print("\nSome objects failed. They remain readable under their old key; "
              "investigate before clearing VAULT_ENCRYPTION_KEY.", file=sys.stderr)
        return 1
    else:
        print("\nAll objects re-encrypted. Once verified, clear VAULT_ENCRYPTION_KEY "
              "(the v1 key) to retire it.")
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="perform the rotation")
    sys.exit(asyncio.run(main(parser.parse_args().apply)))
