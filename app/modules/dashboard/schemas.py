"""Dashboard schemas."""

from decimal import Decimal
from pydantic import BaseModel


class DashboardStatsResponse(BaseModel):
    """Aggregated counts for dashboard cards."""

    total_products: int
    active_products: int
    raw_materials_count: int
    low_stock_count: int
    parties_count: int
    work_logs_today: int
    work_logs_this_week: int
    # Production KPIs
    active_batches: int = 0
    units_on_floor: Decimal = Decimal("0")
    completed_batches_month: int = 0
    completed_units_month: Decimal = Decimal("0")


class ProductionTrendItem(BaseModel):
    """Daily production aggregate for chart."""

    date: str
    work_log_count: int
    total_amount: Decimal


class ProductionTrendResponse(BaseModel):
    """Production trend for last N days."""

    items: list[ProductionTrendItem]