"""Dashboard schemas."""

from decimal import Decimal
from typing import List, Optional
from pydantic import BaseModel


class LowStockItem(BaseModel):
    id: int
    name: str
    stock_qty: Decimal
    min_stock_req: Optional[Decimal] = None
    unit_type: str


class FloorStageItem(BaseModel):
    stage_id: int
    stage_name: str
    sequence: int
    batch_count: int
    unit_count: Decimal


class DailyCompletion(BaseModel):
    date: str        # YYYY-MM-DD
    units: Decimal


class DashboardStatsResponse(BaseModel):
    """Everything the dashboard needs — one round-trip."""

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
    # Embedded detail — eliminates separate check-stock, batches, stages, register calls
    low_stock_materials: List[LowStockItem] = []
    floor_by_stage: List[FloorStageItem] = []
    daily_completions: List[DailyCompletion] = []   # last 30 days


class ProductionTrendItem(BaseModel):
    """Daily production aggregate for chart."""

    date: str
    work_log_count: int
    total_amount: Decimal


class ProductionTrendResponse(BaseModel):
    """Production trend for last N days."""

    items: list[ProductionTrendItem]