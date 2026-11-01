import uuid

from fastapi import HTTPException, status
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.material import MaterialStatus, RawMaterialListing
from app.db.models.user import User


async def create_material(
    db: AsyncSession, seller_id: uuid.UUID, data: dict
) -> RawMaterialListing:
    material = RawMaterialListing(seller_id=seller_id, **data)
    db.add(material)
    await db.commit()
    await db.refresh(material)

    from app.core import metrics
    metrics.materials_created_total.inc()

    return material


async def get_material(db: AsyncSession, material_id: uuid.UUID) -> RawMaterialListing | None:
    return await db.get(RawMaterialListing, material_id)


async def get_material_with_seller(
    db: AsyncSession, material_id: uuid.UUID
) -> tuple[RawMaterialListing, str, str] | None:
    result = await db.execute(
        select(RawMaterialListing, User.full_name, User.email)
        .join(User, User.id == RawMaterialListing.seller_id)
        .where(RawMaterialListing.id == material_id)
    )
    row = result.first()
    return (row[0], row[1], row[2]) if row else None


async def get_seller_materials(db: AsyncSession, seller_id: uuid.UUID) -> list[RawMaterialListing]:
    result = await db.execute(
        select(RawMaterialListing)
        .where(RawMaterialListing.seller_id == seller_id)
        .order_by(RawMaterialListing.created_at.desc())
    )
    return list(result.scalars().all())


async def browse_materials(
    db: AsyncSession,
    *,
    q: str | None = None,
    category: str | None = None,
    region: str | None = None,
    country: str | None = None,
    limit: int = 20,
    offset: int = 0,
) -> list[tuple[RawMaterialListing, str, str]]:
    """Active material listings with seller identity, newest first.

    region/country are substring matches so 'gujarat' finds 'Gujarat, Western India'.
    """
    stmt = (
        select(RawMaterialListing, User.full_name, User.email)
        .join(User, User.id == RawMaterialListing.seller_id)
        .where(RawMaterialListing.status == MaterialStatus.ACTIVE)
    )
    if q:
        pattern = f"%{q}%"
        stmt = stmt.where(
            or_(RawMaterialListing.title.ilike(pattern), RawMaterialListing.description.ilike(pattern))
        )
    if category:
        stmt = stmt.where(RawMaterialListing.category == category)
    if region:
        stmt = stmt.where(RawMaterialListing.region.ilike(f"%{region}%"))
    if country:
        stmt = stmt.where(RawMaterialListing.country.ilike(f"%{country}%"))

    stmt = stmt.order_by(RawMaterialListing.created_at.desc()).limit(limit).offset(offset)
    result = await db.execute(stmt)
    return [(row[0], row[1], row[2]) for row in result.all()]


async def update_material(
    db: AsyncSession, material: RawMaterialListing, changes: dict
) -> RawMaterialListing:
    for field, value in changes.items():
        setattr(material, field, value)
    await db.commit()
    await db.refresh(material)
    return material


async def archive_material(db: AsyncSession, material: RawMaterialListing) -> RawMaterialListing:
    material.status = MaterialStatus.ARCHIVED
    await db.commit()
    await db.refresh(material)
    return material


def require_seller(material: RawMaterialListing, user_id: uuid.UUID) -> None:
    if material.seller_id != user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not your material listing")


async def count_active_materials(db: AsyncSession) -> int:
    result = await db.execute(
        select(func.count())
        .select_from(RawMaterialListing)
        .where(RawMaterialListing.status == MaterialStatus.ACTIVE)
    )
    return int(result.scalar_one())
