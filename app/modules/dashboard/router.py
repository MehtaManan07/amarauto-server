"""Dashboard router - stats for dashboard cards."""

from fastapi import APIRouter, Depends

from app.modules.users.auth import TokenData, require_any_role
from .service import DashboardService
from .schemas import DashboardStatsResponse

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/stats", response_model=DashboardStatsResponse)
async def get_dashboard_stats(
    current_user: TokenData = Depends(require_any_role),
):
    """Return counts for dashboard cards. No full data - counts only."""
    return await DashboardService.get_stats()
