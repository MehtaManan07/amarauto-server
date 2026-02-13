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
    RawMaterialPaginatedResponse,
    StockCheckResponse,
    BulkUploadResponse,
    FieldOptionsResponse,
    AdjustStockRequest,
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


@router.get("", response_model=RawMaterialPaginatedResponse)
async def list_raw_materials(
    search: Optional[str] = Query(None, description="Search across name, unit_type, material_type, group, description (words AND'd)"),
    page: int = Query(1, ge=1, description="Page number (1-indexed)"),
    page_size: int = Query(25, ge=1, le=1000, description="Items per page (max 1000)"),
    current_user: TokenData = Depends(require_any_role),
):
    """List raw materials with pagination. Optional search. Returns items, total, page, page_size, total_pages, has_more."""
    return await RawMaterialService.find_all_paginated(
        page=page,
        page_size=page_size,
        search=search,
    )


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


@router.get("/field-options", response_model=FieldOptionsResponse)
async def get_field_options(
    fields: Optional[str] = Query(
        None,
        description="Comma-separated field names: unit_type, material_type, group. Omit for all.",
    ),
    current_user: TokenData = Depends(require_any_role),
):
    """Unique values for selectable fields. Frontend can show dropdowns; users can still enter new values."""
    field_list = [f.strip() for f in fields.split(",")] if fields else None
    data = await RawMaterialService.get_field_options(fields=field_list)
    return FieldOptionsResponse(**data)


@router.post("/{material_id}/adjust-stock", response_model=RawMaterialResponse)
async def adjust_stock(
    material_id: int,
    dto: AdjustStockRequest,
    current_user: TokenData = Depends(require_any_role),
):
    """Adjust stock (add or remove) and create inventory log. Delta > 0 = add, Delta < 0 = remove."""
    return await RawMaterialService.adjust_stock(
        material_id=material_id,
        quantity_delta=dto.quantity_delta,
        notes=dto.notes,
        user_id=current_user.user_id,
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
