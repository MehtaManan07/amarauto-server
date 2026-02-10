"""
BOM router. CRUD + list by product/variant. List supports powerful search.
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, Query

from app.core.response_interceptor import skip_interceptor
from app.modules.users.auth import TokenData, require_any_role
from .service import BOMService
from .schemas import BOMLineCreateDto, BOMLineUpdateDto, BOMLineResponse

router = APIRouter(prefix="/bom", tags=["bom"])


@router.post("", response_model=BOMLineResponse)
async def create_bom_line(
    dto: BOMLineCreateDto,
    current_user: TokenData = Depends(require_any_role),
):
    """Add a BOM line (product + raw material + variant + quantities)."""
    return await BOMService.create(dto)


@router.get("", response_model=List[BOMLineResponse])
async def list_bom_lines(
    search: Optional[str] = Query(None, description="Search raw material name, variant (words AND'd)"),
    product_id: Optional[int] = Query(None, description="Filter by product"),
    variant: Optional[str] = Query(None, description="Filter by variant e.g. colour"),
    current_user: TokenData = Depends(require_any_role),
):
    """List BOM lines. Optional search and product_id / variant filters."""
    return await BOMService.find_all(
        search=search,
        product_id=product_id,
        variant=variant,
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
