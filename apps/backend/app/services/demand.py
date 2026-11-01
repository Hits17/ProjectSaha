"""
Demand intelligence: aggregates the demand_signals captured on every search into
actionable insight for creators — what manufacturers are searching for, and where
demand goes unmet (zero-result searches = listing opportunities).
"""

import structlog
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

logger = structlog.get_logger()

_WINDOW = "created_at >= NOW() - (:days * INTERVAL '1 day')"


async def get_demand_overview(db: AsyncSession, days: int = 30, limit: int = 10) -> dict:
    params = {"days": days, "limit": limit}

    totals = (await db.execute(text(
        f"SELECT COUNT(*) AS total, COUNT(DISTINCT user_id) AS searchers, "
        f"COALESCE(SUM(CASE WHEN result_count = 0 THEN 1 ELSE 0 END), 0) AS unmet "
        f"FROM demand_signals WHERE {_WINDOW}"
    ), params)).one()

    top_queries = (await db.execute(text(
        f"SELECT LOWER(TRIM(query_text)) AS q, COUNT(*) AS n, ROUND(AVG(result_count), 1) AS avg_results "
        f"FROM demand_signals WHERE {_WINDOW} AND TRIM(query_text) <> '' "
        f"GROUP BY LOWER(TRIM(query_text)) ORDER BY n DESC, q ASC LIMIT :limit"
    ), params)).all()

    demand_gaps = (await db.execute(text(
        f"SELECT LOWER(TRIM(query_text)) AS q, COUNT(*) AS n "
        f"FROM demand_signals WHERE {_WINDOW} AND result_count = 0 AND TRIM(query_text) <> '' "
        f"GROUP BY LOWER(TRIM(query_text)) ORDER BY n DESC, q ASC LIMIT :limit"
    ), params)).all()

    top_industries = (await db.execute(text(
        f"SELECT parsed_intent->>'industry' AS k, COUNT(*) AS n "
        f"FROM demand_signals WHERE {_WINDOW} AND parsed_intent->>'industry' IS NOT NULL "
        f"AND parsed_intent->>'industry' <> '' "
        f"GROUP BY parsed_intent->>'industry' ORDER BY n DESC LIMIT :limit"
    ), params)).all()

    top_product_types = (await db.execute(text(
        f"SELECT parsed_intent->>'product_type' AS k, COUNT(*) AS n "
        f"FROM demand_signals WHERE {_WINDOW} AND parsed_intent->>'product_type' IS NOT NULL "
        f"AND parsed_intent->>'product_type' <> '' "
        f"GROUP BY parsed_intent->>'product_type' ORDER BY n DESC LIMIT :limit"
    ), params)).all()

    return {
        "window_days": days,
        "total_searches": int(totals.total),
        "unique_searchers": int(totals.searchers or 0),
        "unmet_searches": int(totals.unmet),
        "top_queries": [
            {"query": r.q, "count": int(r.n), "avg_results": float(r.avg_results or 0)} for r in top_queries
        ],
        "demand_gaps": [{"query": r.q, "count": int(r.n)} for r in demand_gaps],
        "top_industries": [{"label": r.k, "count": int(r.n)} for r in top_industries],
        "top_product_types": [{"label": r.k, "count": int(r.n)} for r in top_product_types],
    }
