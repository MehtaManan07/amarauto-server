"""Production router - stage completion and WIP inventory."""

from typing import List, Optional
from fastapi import APIRouter, Depends, Query
from decimal import Decimal

from app.modules.users.auth import TokenData, require_any_role
from .service import ProductionService
from .schemas import (
    StageCompletionDto,
    StageCompletionResponse,
    StageInventoryResponse,
    MaterialsPreviewResponse,
)

router = APIRouter(prefix="/production", tags=["production"])


@router.post("/complete-stage", response_model=StageCompletionResponse)
async def complete_stage(
    dto: StageCompletionDto,
    current_user: TokenData = Depends(require_any_role),
):
    """Complete a production stage: deduct materials, move quantity to stage."""
    return await ProductionService.complete_stage(
        dto,
        user_id=current_user.user_id,
    )


@router.get("/stage-inventory", response_model=List[StageInventoryResponse])
async def get_stage_inventory(
    product_id: Optional[int] = Query(None, description="Filter by product"),
    variant: Optional[str] = Query(None, description="Filter by variant"),
    stage_number: Optional[int] = Query(None, ge=1, description="Filter by stage"),
    current_user: TokenData = Depends(require_any_role),
):
    """Get WIP quantities at each stage."""
    return await ProductionService.get_stage_inventory(
        product_id=product_id,
        variant=variant,
        stage_number=stage_number,
    )


@router.get("/materials-preview", response_model=MaterialsPreviewResponse)
async def get_materials_preview(
    product_id: int = Query(..., description="Product ID"),
    variant: Optional[str] = Query(None, description="Variant"),
    stage_number: int = Query(..., ge=1, description="Stage number"),
    quantity: Decimal = Query(..., gt=0, description="Quantity to complete"),
    current_user: TokenData = Depends(require_any_role),
):
    """Preview materials needed before completing a stage."""
    return await ProductionService.get_materials_preview(
        product_id=product_id,
        variant=variant,
        stage_number=stage_number,
        quantity=quantity,
    )
