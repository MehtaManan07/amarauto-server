"""Inventory logs router - get logs for raw materials."""

from fastapi import APIRouter, Depends, Query

from app.modules.users.auth import TokenData, require_any_role
from .service import InventoryLogService

router = APIRouter(prefix="/inventory-logs", tags=["inventory-logs"])


@router.get("/raw-material/{raw_material_id}")
async def get_inventory_logs(
    raw_material_id: int,
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(25, ge=1, le=100, description="Items per page"),
    current_user: TokenData = Depends(require_any_role),
):
    """Get inventory log entries for a raw material, newest first, with pagination."""
    return await InventoryLogService.get_logs_by_raw_material(
        raw_material_id, page=page, page_size=page_size
    )
