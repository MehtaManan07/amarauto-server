"""
Work logs router (new schema). Piece-rate labor + payroll.
Create/bulk/update/delete: Admin/Supervisor only (workers are dropdown/payroll subjects).
Reads + payroll: any authenticated role.
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
    WorkLogBulkCreateDto,
    WorkLogResponse,
    WorkLogPaginatedResponse,
    BulkCreateResponse,
    PayrollResponse,
)

router = APIRouter(prefix="/work-logs", tags=["work-logs"])


@router.post("", response_model=WorkLogResponse)
async def create_work_log(
    dto: WorkLogCreateDto,
    current_user: TokenData = Depends(require_admin_or_supervisor),
):
    """Log one piece-rate entry. rate defaults to the operation's rate; pay = quantity * rate."""
    return await WorkLogService.create(dto)


@router.post("/bulk", response_model=BulkCreateResponse)
async def bulk_create_work_logs(
    dto: WorkLogBulkCreateDto,
    current_user: TokenData = Depends(require_admin_or_supervisor),
):
    """Bulk-log many entries for ONE worker in a single transaction (the worklog grid)."""
    return await WorkLogService.bulk_create(dto)


@router.get("", response_model=WorkLogPaginatedResponse)
async def list_work_logs(
    search: Optional[str] = Query(None, description="Search worker, operation code/name, notes"),
    worker_id: Optional[int] = Query(None, gt=0),
    operation_id: Optional[int] = Query(None, gt=0),
    batch_id: Optional[int] = Query(None, gt=0),
    from_date: Optional[date] = Query(None, description="work_date >= (YYYY-MM-DD)"),
    to_date: Optional[date] = Query(None, description="work_date <= (YYYY-MM-DD)"),
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=1000),
    current_user: TokenData = Depends(require_any_role),
):
    """List work logs with pagination + filters (worker / operation / batch / date range)."""
    return await WorkLogService.find_all_paginated(
        page=page, page_size=page_size, search=search,
        worker_id=worker_id, operation_id=operation_id, batch_id=batch_id,
        from_date=from_date, to_date=to_date,
    )


@router.get("/payroll", response_model=PayrollResponse)
async def payroll(
    from_date: date = Query(..., description="Period start (YYYY-MM-DD)"),
    to_date: date = Query(..., description="Period end (YYYY-MM-DD)"),
    worker_id: Optional[int] = Query(None, gt=0, description="Limit to one worker"),
    current_user: TokenData = Depends(require_any_role),
):
    """Payroll: sum(quantity) and sum(total_amount) per worker over the date range."""
    return await WorkLogService.payroll(from_date=from_date, to_date=to_date, worker_id=worker_id)


@router.get("/{log_id}", response_model=WorkLogResponse)
async def get_work_log(
    log_id: int,
    current_user: TokenData = Depends(require_any_role),
):
    """Get one work log."""
    return await WorkLogService.find_one(log_id)


@router.patch("/{log_id}", response_model=WorkLogResponse)
async def update_work_log(
    log_id: int,
    dto: WorkLogUpdateDto,
    current_user: TokenData = Depends(require_admin_or_supervisor),
):
    """Edit a work log. Changing rate/quantity re-snapshots total_amount."""
    return await WorkLogService.update(log_id, dto)


@router.delete("/{log_id}")
@skip_interceptor
async def delete_work_log(
    log_id: int,
    current_user: TokenData = Depends(require_admin_or_supervisor),
):
    """Soft delete a work log."""
    await WorkLogService.remove(log_id)
    return {"message": "Work log deleted successfully"}
