"""
Batches router (production execution). 14a: CRUD + per-stage WIP.
Advance/consume (14b) and rejects (14c) add more endpoints here.
"""

from typing import Optional
from decimal import Decimal
from fastapi import APIRouter, Depends, Query

from app.core.response_interceptor import skip_interceptor
from app.modules.users.auth import TokenData, require_any_role
from .service import BatchService
from .schemas import (
    BatchCreateDto,
    BatchUpdateDto,
    BatchAdvanceDto,
    BatchRejectDto,
    BatchDetailResponse,
    BatchPaginatedResponse,
    MaterialPreviewResponse,
)

router = APIRouter(prefix="/batches", tags=["batches"])


@router.post("", response_model=BatchDetailResponse)
async def create_batch(
    dto: BatchCreateDto,
    current_user: TokenData = Depends(require_any_role),
):
    """Create a batch: records an intake movement of `quantity` units into the first stage."""
    return await BatchService.create(dto, user_id=current_user.user_id)


@router.get("", response_model=BatchPaginatedResponse)
async def list_batches(
    search: Optional[str] = Query(None, description="Search batch_no, style, colour, product (words AND'd)"),
    product_id: Optional[int] = Query(None, gt=0, description="Filter by product"),
    status: Optional[str] = Query(None, description="Filter by status (open/in_progress/done/cancelled)"),
    page: int = Query(1, ge=1, description="Page number (1-indexed)"),
    page_size: int = Query(25, ge=1, le=1000, description="Items per page (max 1000)"),
    current_user: TokenData = Depends(require_any_role),
):
    """List batches with pagination. Each row includes its derived current stage."""
    return await BatchService.find_all_paginated(
        page=page,
        page_size=page_size,
        search=search,
        product_id=product_id,
        status=status,
    )


@router.get("/{batch_id}", response_model=BatchDetailResponse)
async def get_batch(
    batch_id: int,
    current_user: TokenData = Depends(require_any_role),
):
    """Get a batch with its full per-stage WIP breakdown."""
    return await BatchService.find_one(batch_id)


@router.post("/{batch_id}/advance", response_model=BatchDetailResponse)
async def advance_batch(
    batch_id: int,
    dto: BatchAdvanceDto,
    current_user: TokenData = Depends(require_any_role),
):
    """Move units to the next stage. Consumes that stage's BOM (warn-and-allow on negative
    stock). `consumption` + `warnings` in the response describe what was deducted."""
    return await BatchService.advance(batch_id, dto, user_id=current_user.user_id)


@router.post("/{batch_id}/reject", response_model=BatchDetailResponse)
async def reject_batch(
    batch_id: int,
    dto: BatchRejectDto,
    current_user: TokenData = Depends(require_any_role),
):
    """Record scrap of N units at a stage. Shrinks that stage's WIP; does not refund materials."""
    return await BatchService.reject(batch_id, dto, user_id=current_user.user_id)


@router.get("/{batch_id}/material-preview", response_model=MaterialPreviewResponse)
async def material_preview(
    batch_id: int,
    stage_id: int = Query(..., gt=0, description="Stage to move into"),
    quantity: Decimal = Query(..., gt=0, description="Units to move"),
    current_user: TokenData = Depends(require_any_role),
):
    """Preview what moving `quantity` units into `stage_id` would consume (no writes)."""
    return await BatchService.material_preview(batch_id, stage_id, quantity)


@router.patch("/{batch_id}", response_model=BatchDetailResponse)
async def update_batch(
    batch_id: int,
    dto: BatchUpdateDto,
    current_user: TokenData = Depends(require_any_role),
):
    """Light edits (style/colour/status). Quantities move via advance/reject, not here."""
    return await BatchService.update(batch_id, dto)


@router.delete("/{batch_id}")
@skip_interceptor
async def delete_batch(
    batch_id: int,
    current_user: TokenData = Depends(require_any_role),
):
    """Soft delete a batch."""
    await BatchService.remove(batch_id)
    return {"message": "Batch deleted successfully"}
