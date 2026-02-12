"""Dashboard schemas."""

from pydantic import BaseModel


class DashboardStatsResponse(BaseModel):
    """Aggregated counts for dashboard cards."""

    total_products: int
    active_products: int
    raw_materials_count: int
    low_stock_count: int
