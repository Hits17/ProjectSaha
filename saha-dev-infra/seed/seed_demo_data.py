#!/usr/bin/env python3
"""Seed the Saha database with demo data for manual testing.

Populates:
  • The Open Innovation Library with 100+ real, web-verified open-source
    resources (expired/pledged patents, CC-BY research papers, genericized
    trademarks) — inserted as admin-curated, approved, publicly visible.
  • 10 verified "creator" test users, each with 10 published IP listings built
    on real expired patents (100 listings total). Each listing carries a BOM and
    is pushed through the normal publish path so it is indexed into Qdrant for
    semantic search / demand features.

Run it from the backend app so its .env / config / models all load:

    cd apps/backend
    uv run python ../../saha-dev-infra/seed/seed_demo_data.py            # apply
    uv run python ../../saha-dev-infra/seed/seed_demo_data.py --dry-run  # validate only

Idempotent: users are keyed by email, library entries by (identifier or
source_url), listings by (creator, title). Re-running skips what already exists.

PREREQUISITE: the 'trademark' value must exist on the open_resource_type enum.
Apply the migration first (as postgres, outside a transaction):
    sudo -u postgres psql -d saha -c \
      "ALTER TYPE open_resource_type ADD VALUE IF NOT EXISTS 'trademark';"
"""
import argparse
import asyncio
import json
import pathlib
import sys

from sqlalchemy import func, select

# Ensure the backend package is importable regardless of CWD.
BACKEND = pathlib.Path(__file__).resolve().parents[2] / "apps" / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from app.core.security import hash_password  # noqa: E402
from app.db.models.listing import BOMItem, IPListing, ListingStatus  # noqa: E402
from app.db.models.open_resource import (  # noqa: E402
    OpenResource,
    OpenResourceStatus,
    OpenResourceType,
)
from app.db.models.user import KYCStatus, User, UserRole  # noqa: E402
from app.db.session import AsyncSessionLocal  # noqa: E402
from app.services import listings as listing_svc  # noqa: E402

DATA = pathlib.Path(__file__).resolve().parent / "data"
DEMO_PASSWORD = "SahaDemo#2026!"  # ≥12 chars, letters+digits — satisfies the policy
EMBED_PAUSE_SECONDS = 0.6  # be gentle on the NVIDIA embedding API between listings


def load(name):
    return json.loads((DATA / name).read_text())


async def get_admin_id(db):
    """added_by for library entries — reuse an existing admin, else any user."""
    admin_id = (await db.execute(
        select(User.id).where(User.role == UserRole.ADMIN, User.is_active.is_(True)).limit(1)
    )).scalar_one_or_none()
    if admin_id is None:
        admin_id = (await db.execute(select(User.id).limit(1))).scalar_one_or_none()
    return admin_id


async def seed_users(db, personas, dry_run):
    created = skipped = 0
    ids = {}
    for p in personas:
        existing = (await db.execute(
            select(User).where(User.email == p["email"])
        )).scalar_one_or_none()
        if existing:
            ids[p["email"]] = existing.id
            skipped += 1
            continue
        user = User(
            email=p["email"],
            hashed_password=hash_password(DEMO_PASSWORD),
            full_name=p["full_name"],
            role=UserRole.CREATOR,
            kyc_status=KYCStatus.VERIFIED,
            is_active=True,
            email_verified=True,
            email_verified_at=func.now(),
        )
        db.add(user)
        if not dry_run:
            await db.flush()
        ids[p["email"]] = user.id
        created += 1
    if not dry_run:
        await db.commit()
    print(f"  users:   {created} created, {skipped} existing")
    return ids


async def seed_library(db, entries, admin_id, dry_run):
    created = skipped = 0
    for e in entries:
        # Natural key: identifier if present, else source_url.
        clause = (OpenResource.identifier == e["identifier"]) if e.get("identifier") \
            else (OpenResource.source_url == e["source_url"])
        exists = (await db.execute(
            select(OpenResource.id).where(clause).limit(1)
        )).scalar_one_or_none()
        if exists:
            skipped += 1
            continue
        db.add(OpenResource(
            resource_type=OpenResourceType(e["resource_type"]),
            title=e["title"],
            summary=e.get("summary"),
            authors=e.get("authors"),
            organization=e.get("organization"),
            identifier=e.get("identifier"),
            source_url=e["source_url"],
            license=e["license"],
            category=e.get("category"),
            tags=e.get("tags") or [],
            published_year=e.get("published_year"),
            status=OpenResourceStatus.APPROVED,
            is_active=True,
            added_by=admin_id,
        ))
        created += 1
    if not dry_run:
        await db.commit()
    print(f"  library: {created} created, {skipped} existing")
    return created, skipped


async def seed_listings(db, payload, user_ids, dry_run):
    created = skipped = failed = 0
    no_vector = []
    listings = payload["listings"]
    for i, item in enumerate(listings, 1):
        creator_id = user_ids.get(item["persona_email"])
        if creator_id is None:
            failed += 1
            continue
        exists = (await db.execute(
            select(IPListing.id).where(
                IPListing.creator_id == creator_id,
                IPListing.title == item["title"][:500],
            ).limit(1)
        )).scalar_one_or_none()
        if exists:
            skipped += 1
            continue

        listing = IPListing(
            creator_id=creator_id,
            title=item["title"][:500],
            description=item.get("description"),
            product_category=item.get("product_category"),
            tags=item.get("tags") or [],
            public_description=item["public_description"],
            status=ListingStatus.REVIEW,  # publish_listing requires REVIEW
        )
        for b in item.get("bom", []):
            listing.bom_items.append(BOMItem(
                material_name=b["material_name"],
                specification=b.get("specification"),
                quantity_per_unit=b["quantity_per_unit"],
                unit_of_measure=b["unit_of_measure"],
                is_critical=b.get("is_critical", False),
            ))

        if dry_run:
            created += 1
            continue

        db.add(listing)
        await db.commit()
        await db.refresh(listing)
        try:
            # Normal publish path: embeds into Qdrant and flips to PUBLISHED.
            # publish_listing already tolerates embedding/Qdrant failure (logs a
            # warning and still publishes), so a listing may end up without a vector.
            listing = await listing_svc.publish_listing(db, listing)
            if listing.qdrant_point_id is None:
                no_vector.append(item["title"][:60])
            created += 1
        except Exception as ex:  # unexpected — leave it in REVIEW and keep going
            failed += 1
            print(f"    ! publish failed for '{item['title'][:50]}': {ex}")
        await asyncio.sleep(EMBED_PAUSE_SECONDS)
        if i % 20 == 0:
            print(f"    … {i}/{len(listings)} listings processed")

    print(f"  listings: {created} created, {skipped} existing, {failed} failed")
    if no_vector:
        print(f"    ⚠ {len(no_vector)} listing(s) published WITHOUT a Qdrant vector "
              f"(embedding API unavailable): {', '.join(no_vector[:5])}"
              + (" …" if len(no_vector) > 5 else ""))
    return created, skipped, failed, no_vector


async def main(dry_run):
    personas = load("listings.json")["personas"]
    library = load("open_resources.json")
    listings_payload = load("listings.json")

    print(f"{'DRY RUN — ' if dry_run else ''}Seeding Saha demo data")
    print(f"  datasets: {len(library)} library entries, "
          f"{len(listings_payload['listings'])} listings, {len(personas)} personas")

    async with AsyncSessionLocal() as db:
        admin_id = await get_admin_id(db)
        if admin_id is None:
            print("  ! No users exist yet — create an admin before seeding the library.")
            return 1
        user_ids = await seed_users(db, personas, dry_run)
        await seed_library(db, library, admin_id, dry_run)
        await seed_listings(db, listings_payload, user_ids, dry_run)

    print("Done." if not dry_run else "Dry run complete — nothing written.")
    return 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Seed Saha demo data")
    ap.add_argument("--dry-run", action="store_true",
                    help="Validate datasets and resolve keys without writing.")
    args = ap.parse_args()
    raise SystemExit(asyncio.run(main(args.dry_run)))
