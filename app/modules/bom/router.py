"""
BOM router (new production-flow schema). CRUD + list (filterable), variants, production calc.
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
    BOMVariantResponse,
    ProductionCalcResponse,
)

router = APIRouter(prefix="/bom", tags=["bom"])


@router.post("", response_model=BOMLineResponse)
async def create_bom_line(
    dto: BOMLineCreateDto,
    current_user: TokenData = Depends(require_any_role),
):
    """Add a BOM line (product + stage + style/colour + raw material + quantities).
    Duplicate lines are intentional and never merged (sum-don't-dedup)."""
    return await BOMService.create(dto)


@router.get("", response_model=BOMPaginatedResponse)
async def list_bom_lines(
    search: Optional[str] = Query(None, description="Search raw material name, style, colour (words AND'd)"),
    product_id: Optional[int] = Query(None, gt=0, description="Filter by product"),
    raw_material_id: Optional[int] = Query(None, gt=0, description="Filter by raw material"),
    stage_id: Optional[int] = Query(None, gt=0, description="Filter by stage"),
    style: Optional[str] = Query(None, description="Filter by style (texture)"),
    colour: Optional[str] = Query(None, description="Filter by colour"),
    page: int = Query(1, ge=1, description="Page number (1-indexed)"),
    page_size: int = Query(25, ge=1, le=1000, description="Items per page (max 1000)"),
    current_user: TokenData = Depends(require_any_role),
):
    """List BOM lines with pagination. Optional search + product/raw_material/stage/style/colour filters."""
    return await BOMService.find_all_paginated(
        page=page,
        page_size=page_size,
        search=search,
        product_id=product_id,
        raw_material_id=raw_material_id,
        stage_id=stage_id,
        style=style,
        colour=colour,
    )


@router.get("/variants", response_model=List[BOMVariantResponse])
async def get_bom_variants(
    product_id: int = Query(..., gt=0, description="Product to get style/colour variants for"),
    current_user: TokenData = Depends(require_any_role),
):
    """Distinct style x colour combos a product has a BOM for."""
    return await BOMService.get_variants(product_id)


@router.get("/production-calc", response_model=ProductionCalcResponse)
async def get_production_calc(
    product_id: int = Query(..., gt=0, description="Product ID"),
    quantity: int = Query(..., ge=1, description="Quantity to produce"),
    style: Optional[str] = Query(None, description="Style (texture)"),
    colour: Optional[str] = Query(None, description="Colour"),
    current_user: TokenData = Depends(require_any_role),
):
    """Calculate material requirements and order cost for producing units of a variant."""
    return await BOMService.get_production_calc(
        product_id=product_id,
        quantity=quantity,
        style=style,
        colour=colour,
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
