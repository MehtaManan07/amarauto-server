"""
Work logs router. CRUD with pagination. Create/Update/Delete: Admin/Supervisor only.
"""

from typing import Optional
from datetime import date
from fastapi import APIRouter, Depends, Query

from app.core.response_interceptor import skip_interceptor
from app.modules.users.auth import TokenData, require_any_role, require_admin_or_supervisor
from .service import WorkLogService
from .schemas import (
    WorkLogCreateDto,
    WorkLogUpdateDto,
    WorkLogResponse,
    WorkLogPaginatedResponse,
)

router = APIRouter(prefix="/work-logs", tags=["work-logs"])


@router.post("", response_model=WorkLogResponse)
async def create_work_log(
    dto: WorkLogCreateDto,
    current_user: TokenData = Depends(require_admin_or_supervisor),
):
    """Add a work log (Admin/Supervisor only)."""
    return await WorkLogService.create(dto)


@router.get("", response_model=WorkLogPaginatedResponse)
async def list_work_logs(
    user_id: Optional[int] = Query(None, description="Filter by worker"),
    product_id: Optional[int] = Query(None, description="Filter by product"),
    job_rate_id: Optional[int] = Query(None, description="Filter by job rate"),
    work_date_from: Optional[date] = Query(None, description="From date"),
    work_date_to: Optional[date] = Query(None, description="To date"),
    search: Optional[str] = Query(None, description="Search user, product, operation (words AND'd)"),
    page: int = Query(1, ge=1, description="Page number (1-indexed)"),
    page_size: int = Query(25, ge=1, le=1000, description="Items per page (max 1000)"),
    current_user: TokenData = Depends(require_any_role),
):
    """List work logs with pagination and filters."""
    return await WorkLogService.find_all_paginated(
        page=page,
        page_size=page_size,
        user_id=user_id,
        product_id=product_id,
        job_rate_id=job_rate_id,
        work_date_from=work_date_from,
        work_date_to=work_date_to,
        search=search,
    )


@router.get("/{log_id}", response_model=WorkLogResponse)
async def get_work_log(
    log_id: int,
    current_user: TokenData = Depends(require_any_role),
):
    """Get work log by id."""
    return await WorkLogService.find_one(log_id)


@router.patch("/{log_id}", response_model=WorkLogResponse)
async def update_work_log(
    log_id: int,
    dto: WorkLogUpdateDto,
    current_user: TokenData = Depends(require_admin_or_supervisor),
):
    """Update work log (Admin/Supervisor only)."""
    return await WorkLogService.update(log_id, dto)


@router.delete("/{log_id}")
@skip_interceptor
async def delete_work_log(
    log_id: int,
    current_user: TokenData = Depends(require_admin_or_supervisor),
):
    """Soft delete work log (Admin/Supervisor only)."""
    await WorkLogService.remove(log_id)
    return {"message": "Work log deleted successfully"}
