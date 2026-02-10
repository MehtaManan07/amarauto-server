"""
Raw materials router. CRUD + check stock. List supports powerful search.
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, Query

from app.core.response_interceptor import skip_interceptor
from app.modules.users.auth import get_current_user, TokenData, require_any_role
from .service import RawMaterialService
from .schemas import (
    RawMaterialCreateDto,
    RawMaterialUpdateDto,
    RawMaterialResponse,
    StockCheckResponse,
    BulkUploadResponse,
)

router = APIRouter(prefix="/raw-materials", tags=["raw-materials"])


@router.post("", response_model=RawMaterialResponse)
async def create_raw_material(
    dto: RawMaterialCreateDto,
    current_user: TokenData = Depends(require_any_role),
):
    """Add a raw material."""
    return await RawMaterialService.create(dto)


@router.post("/bulk", response_model=BulkUploadResponse)
async def bulk_upload_raw_materials(
    items: List[RawMaterialCreateDto],
    current_user: TokenData = Depends(require_any_role),
):
    """
    Bulk upload raw materials. Each item is processed independently.
    Returns detailed results showing successes and failures for each item.
    """
    return await RawMaterialService.bulk_create(items)


@router.get("", response_model=List[RawMaterialResponse])
async def list_raw_materials(
    search: Optional[str] = Query(None, description="Search across name, unit_type, material_type, group, description (words AND'd)"),
    current_user: TokenData = Depends(require_any_role),
):
    """List raw materials. Optional search: split into words, each word matches any field."""
    return await RawMaterialService.find_all(search=search)


@router.get("/check-stock", response_model=List[StockCheckResponse])
async def check_stock(
    below_min_only: bool = Query(True, description="If true, only items where stock_qty < min_stock_req"),
    search: Optional[str] = Query(None, description="Filter by search (same as list)"),
    current_user: TokenData = Depends(require_any_role),
):
    """Check stock levels. Use below_min_only=true for items below minimum only."""
    return await RawMaterialService.check_stock(
        below_min_only=below_min_only,
        search=search,
    )


@router.get("/{material_id}", response_model=RawMaterialResponse)
async def get_raw_material(
    material_id: int,
    current_user: TokenData = Depends(require_any_role),
):
    """Get raw material by id."""
    return await RawMaterialService.find_one(material_id)


@router.patch("/{material_id}", response_model=RawMaterialResponse)
async def update_raw_material(
    material_id: int,
    dto: RawMaterialUpdateDto,
    current_user: TokenData = Depends(require_any_role),
):
    """Update raw material (including stock_qty)."""
    return await RawMaterialService.update(material_id, dto)


@router.delete("/{material_id}")
@skip_interceptor
async def delete_raw_material(
    material_id: int,
    current_user: TokenData = Depends(require_any_role),
):
    """Soft delete raw material."""
    await RawMaterialService.remove(material_id)
    return {"message": "Raw material deleted successfully"}
