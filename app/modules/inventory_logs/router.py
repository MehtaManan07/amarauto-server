"""Inventory logs router - get logs for raw materials."""

from typing import List
from fastapi import APIRouter, Depends

from app.modules.users.auth import TokenData, require_any_role
from .service import InventoryLogService
from .schemas import InventoryLogResponse

router = APIRouter(prefix="/inventory-logs", tags=["inventory-logs"])


@router.get(
    "/raw-material/{raw_material_id}",
    response_model=List[InventoryLogResponse],
)
async def get_inventory_logs(
    raw_material_id: int,
    current_user: TokenData = Depends(require_any_role),
):
    """Get inventory log entries for a raw material, newest first."""
    return await InventoryLogService.get_logs_by_raw_material(raw_material_id)
