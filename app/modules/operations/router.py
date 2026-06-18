"""
Operations router. CRUD for paid, piece-rate operations per product/stage.
The list is filterable by product_id / stage_id (recipe editor lists ops by product).
"""

from typing import Optional
from fastapi import APIRouter, Depends, Query

from app.core.response_interceptor import skip_interceptor
from app.modules.users.auth import TokenData, require_any_role
from .service import OperationService
from .schemas import (
    OperationCreateDto,
    OperationUpdateDto,
    OperationResponse,
    OperationPaginatedResponse,
)

router = APIRouter(prefix="/operations", tags=["operations"])


@router.post("", response_model=OperationResponse)
async def create_operation(
    dto: OperationCreateDto,
    current_user: TokenData = Depends(require_any_role),
):
    """Add an operation. code must be unique; product_id (and stage_id if given) must exist."""
    return await OperationService.create(dto)


@router.get("", response_model=OperationPaginatedResponse)
async def list_operations(
    search: Optional[str] = Query(None, description="Search across code, name, component (words AND'd)"),
    product_id: Optional[int] = Query(None, gt=0, description="Filter to one product's operations"),
    stage_id: Optional[int] = Query(None, gt=0, description="Filter to one stage's operations"),
    page: int = Query(1, ge=1, description="Page number (1-indexed)"),
    page_size: int = Query(25, ge=1, le=1000, description="Items per page (max 1000)"),
    current_user: TokenData = Depends(require_any_role),
):
    """List operations with pagination. Optional search + product_id / stage_id filters."""
    return await OperationService.find_all_paginated(
        page=page,
        page_size=page_size,
        search=search,
        product_id=product_id,
        stage_id=stage_id,
    )


@router.get("/{operation_id}", response_model=OperationResponse)
async def get_operation(
    operation_id: int,
    current_user: TokenData = Depends(require_any_role),
):
    """Get an operation by id."""
    return await OperationService.find_one(operation_id)


@router.patch("/{operation_id}", response_model=OperationResponse)
async def update_operation(
    operation_id: int,
    dto: OperationUpdateDto,
    current_user: TokenData = Depends(require_any_role),
):
    """Update an operation (stage, rate, sequence, component, side, etc.)."""
    return await OperationService.update(operation_id, dto)


@router.delete("/{operation_id}")
@skip_interceptor
async def delete_operation(
    operation_id: int,
    current_user: TokenData = Depends(require_any_role),
):
    """Soft delete an operation."""
    await OperationService.remove(operation_id)
    return {"message": "Operation deleted successfully"}
