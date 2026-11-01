from pydantic import BaseModel


class QueryStat(BaseModel):
    query: str
    count: int
    avg_results: float


class GapStat(BaseModel):
    query: str
    count: int


class LabelStat(BaseModel):
    label: str
    count: int


class DemandOverviewResponse(BaseModel):
    window_days: int
    total_searches: int
    unique_searchers: int
    unmet_searches: int
    top_queries: list[QueryStat] = []
    demand_gaps: list[GapStat] = []
    top_industries: list[LabelStat] = []
    top_product_types: list[LabelStat] = []
