"""Dashboard router - stats and chart data."""

from fastapi import APIRouter, Depends, Query

from app.modules.users.auth import TokenData, require_any_role
from .service import DashboardService
from .schemas import DashboardStatsResponse, ProductionTrendResponse

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/stats", response_model=DashboardStatsResponse)
async def get_dashboard_stats(
    current_user: TokenData = Depends(require_any_role),
):
    """Return counts for dashboard cards."""
    return await DashboardService.get_stats()


@router.get("/production-trend", response_model=ProductionTrendResponse)
async def get_production_trend(
    days: int = Query(7, ge=1, le=30, description="Number of days"),
    current_user: TokenData = Depends(require_any_role),
):
    """Return daily production aggregates for last N days."""
    return await DashboardService.get_production_trend(days=days)
