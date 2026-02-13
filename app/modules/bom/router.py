"""
BOM router. CRUD + list by product/variant. List supports powerful search.
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, Query

from app.core.response_interceptor import skip_interceptor
from app.modules.users.auth import TokenData, require_any_role
from .service import BOMService
from .schemas import (
    BOMLineCreateDto,
    BOMLineUpdateDto,
    BOMLineResponse,
    BOMPaginatedResponse,
    ProductionCalcResponse,
)

router = APIRouter(prefix="/bom", tags=["bom"])


@router.post("", response_model=BOMLineResponse)
async def create_bom_line(
    dto: BOMLineCreateDto,
    current_user: TokenData = Depends(require_any_role),
):
    """Add a BOM line (product + raw material + variant + quantities)."""
    return await BOMService.create(dto)


@router.get("", response_model=BOMPaginatedResponse)
async def list_bom_lines(
    search: Optional[str] = Query(None, description="Search raw material name, variant (words AND'd)"),
    product_id: Optional[int] = Query(None, description="Filter by product"),
    raw_material_id: Optional[int] = Query(None, description="Filter by raw material"),
    variant: Optional[str] = Query(None, description="Filter by variant e.g. colour"),
    page: int = Query(1, ge=1, description="Page number (1-indexed)"),
    page_size: int = Query(25, ge=1, le=1000, description="Items per page (max 1000)"),
    current_user: TokenData = Depends(require_any_role),
):
    """List BOM lines with pagination. Optional search and product_id / raw_material_id / variant filters."""
    return await BOMService.find_all_paginated(
        page=page,
        page_size=page_size,
        search=search,
        product_id=product_id,
        raw_material_id=raw_material_id,
        variant=variant,
    )


@router.get("/variants", response_model=List[str])
async def get_bom_variants(
    product_id: int = Query(..., description="Product ID to get variants for"),
    current_user: TokenData = Depends(require_any_role),
):
    """Get distinct variants for a product from BOM lines."""
    return await BOMService.get_variants(product_id)


@router.get("/production-calc", response_model=ProductionCalcResponse)
async def get_production_calc(
    product_id: int = Query(..., description="Product ID"),
    variant: Optional[str] = Query(None, description="Variant (e.g. colour)"),
    quantity: int = Query(..., ge=1, description="Quantity to produce"),
    current_user: TokenData = Depends(require_any_role),
):
    """Calculate material requirements and order cost for producing units."""
    return await BOMService.get_production_calc(
        product_id=product_id,
        variant=variant,
        quantity=quantity,
    )


@router.get("/{line_id}", response_model=BOMLineResponse)
async def get_bom_line(
    line_id: int,
    current_user: TokenData = Depends(require_any_role),
):
    """Get BOM line by id."""
    return await BOMService.find_one(line_id)


@router.patch("/{line_id}", response_model=BOMLineResponse)
async def update_bom_line(
    line_id: int,
    dto: BOMLineUpdateDto,
    current_user: TokenData = Depends(require_any_role),
):
    """Update BOM line."""
    return await BOMService.update(line_id, dto)


@router.delete("/{line_id}")
@skip_interceptor
async def delete_bom_line(
    line_id: int,
    current_user: TokenData = Depends(require_any_role),
):
    """Soft delete BOM line."""
    await BOMService.remove(line_id)
    return {"message": "BOM line deleted successfully"}
