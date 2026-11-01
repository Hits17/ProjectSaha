import uuid

import structlog
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas.material import MaterialCreate, MaterialResponse, MaterialUpdate
from app.core.audit import write_audit_log
from app.core.security import require_verified_user
from app.db.models.material import MaterialStatus
from app.db.models.user import User
from app.db.session import get_db
from app.services import materials as material_svc

router = APIRouter(prefix="/api/v1/materials", tags=["materials"])
logger = structlog.get_logger()


def _with_seller(material, seller_name: str, _seller_email: str | None = None) -> MaterialResponse:
    """Attach the seller's display name. The email is deliberately not carried
    through — see MaterialResponse (security/AUDIT.md SAHA-016)."""
    resp = MaterialResponse.model_validate(material)
    resp.seller_name = seller_name
    return resp


@router.post("", response_model=MaterialResponse, status_code=status.HTTP_201_CREATED)
async def create_material(
    body: MaterialCreate,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_verified_user),
):
    material = await material_svc.create_material(db, current_user.id, body.model_dump())
    background_tasks.add_task(
        write_audit_log,
        action="material.created",
        user_id=current_user.id,
        resource_type="material",
        resource_id=material.id,
        metadata={"title": material.title, "category": material.category, "region": material.region},
    )
    return _with_seller(material, current_user.full_name)


@router.get("/me", response_model=list[MaterialResponse])
async def my_materials(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_verified_user),
):
    materials = await material_svc.get_seller_materials(db, current_user.id)
    return [_with_seller(m, current_user.full_name) for m in materials]


@router.get("", response_model=list[MaterialResponse])
async def browse_materials(
    q: str | None = Query(default=None, max_length=200),
    category: str | None = Query(default=None, max_length=100),
    region: str | None = Query(default=None, max_length=100),
    country: str | None = Query(default=None, max_length=100),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_verified_user),
):
    """Browse active raw-material listings. Verified-only.

    Responses carry the seller's display name but not their email: procurement
    starts through the platform, which is also what keeps the audit trail whole."""
    rows = await material_svc.browse_materials(
        db, q=q, category=category, region=region, country=country, limit=limit, offset=offset
    )
    return [_with_seller(m, name, email) for m, name, email in rows]


@router.get("/{material_id}", response_model=MaterialResponse)
async def get_material(
    material_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_verified_user),
):
    row = await material_svc.get_material_with_seller(db, material_id)
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Material listing not found")
    material, seller_name, seller_email = row
    if material.status != MaterialStatus.ACTIVE and material.seller_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Material listing not found")
    return _with_seller(material, seller_name, seller_email)


@router.patch("/{material_id}", response_model=MaterialResponse)
async def update_material(
    material_id: uuid.UUID,
    body: MaterialUpdate,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_verified_user),
):
    material = await material_svc.get_material(db, material_id)
    if not material:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Material listing not found")
    material_svc.require_seller(material, current_user.id)

    changes = body.model_dump(exclude_unset=True)
    if not changes:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No fields to update")
    material = await material_svc.update_material(db, material, changes)

    background_tasks.add_task(
        write_audit_log,
        action="material.updated",
        user_id=current_user.id,
        resource_type="material",
        resource_id=material.id,
        metadata={"fields": sorted(changes.keys())},
    )
    return _with_seller(material, current_user.full_name)


@router.delete("/{material_id}", response_model=MaterialResponse)
async def archive_material(
    material_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_verified_user),
):
    """Archive (soft-delete): listing disappears from browse but history is kept."""
    material = await material_svc.get_material(db, material_id)
    if not material:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Material listing not found")
    material_svc.require_seller(material, current_user.id)

    material = await material_svc.archive_material(db, material)
    background_tasks.add_task(
        write_audit_log,
        action="material.archived",
        user_id=current_user.id,
        resource_type="material",
        resource_id=material.id,
        metadata={"title": material.title},
    )
    return _with_seller(material, current_user.full_name)
