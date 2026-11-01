from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas.demand import DemandOverviewResponse
from app.core.security import require_verified_user
from app.db.models.user import User
from app.db.session import get_db
from app.services import demand as demand_svc

router = APIRouter(prefix="/api/v1/demand", tags=["demand"])


@router.get("/overview", response_model=DemandOverviewResponse)
async def demand_overview(
    days: int = Query(default=30, ge=1, le=365),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_verified_user),
):
    """Aggregated search-demand intelligence — what manufacturers are looking for,
    and unmet demand (zero-result searches) that creators can fill."""
    return await demand_svc.get_demand_overview(db, days=days)
