"""
Stages router. Config CRUD for the ordered production stages.
"""

from typing import List
from fastapi import APIRouter, Depends, Query

from app.core.response_interceptor import skip_interceptor
from app.modules.users.auth import TokenData, require_any_role
from .service import StageService
from .schemas import StageCreateDto, StageUpdateDto, StageResponse

router = APIRouter(prefix="/stages", tags=["stages"])


@router.post("", response_model=StageResponse)
async def create_stage(
    dto: StageCreateDto,
    current_user: TokenData = Depends(require_any_role),
):
    """Add a production stage."""
    return await StageService.create(dto)


@router.get("", response_model=List[StageResponse])
async def list_stages(
    include_inactive: bool = Query(True, description="Include inactive stages"),
    current_user: TokenData = Depends(require_any_role),
):
    """List stages ordered by sequence (cutting -> stitching -> finishing -> assembly)."""
    return await StageService.find_all(include_inactive=include_inactive)


@router.get("/{stage_id}", response_model=StageResponse)
async def get_stage(
    stage_id: int,
    current_user: TokenData = Depends(require_any_role),
):
    """Get a stage by id."""
    return await StageService.find_one(stage_id)


@router.patch("/{stage_id}", response_model=StageResponse)
async def update_stage(
    stage_id: int,
    dto: StageUpdateDto,
    current_user: TokenData = Depends(require_any_role),
):
    """Update a stage (name, sequence, is_active)."""
    return await StageService.update(stage_id, dto)


@router.delete("/{stage_id}")
@skip_interceptor
async def delete_stage(
    stage_id: int,
    current_user: TokenData = Depends(require_any_role),
):
    """Soft delete a stage."""
    await StageService.remove(stage_id)
    return {"message": "Stage deleted successfully"}
