"""
Job rates (operations) router. CRUD + list by product. List supports powerful search.
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, Query

from app.core.response_interceptor import skip_interceptor
from app.modules.users.auth import TokenData, require_any_role
from .service import JobRateService
from .schemas import JobRateCreateDto, JobRateUpdateDto, JobRateResponse

router = APIRouter(prefix="/job-rates", tags=["job-rates"])


@router.post("", response_model=JobRateResponse)
async def create_job_rate(
    dto: JobRateCreateDto,
    current_user: TokenData = Depends(require_any_role),
):
    """Add an operation (job rate) for a product."""
    return await JobRateService.create(dto)


@router.get("", response_model=List[JobRateResponse])
async def list_job_rates(
    search: Optional[str] = Query(None, description="Search operation_code, operation_name (words AND'd)"),
    product_id: Optional[int] = Query(None, description="Filter by product"),
    current_user: TokenData = Depends(require_any_role),
):
    """List job rates (operations). Optional search and product_id filter."""
    return await JobRateService.find_all(
        search=search,
        product_id=product_id,
    )


@router.get("/{rate_id}", response_model=JobRateResponse)
async def get_job_rate(
    rate_id: int,
    current_user: TokenData = Depends(require_any_role),
):
    """Get job rate by id."""
    return await JobRateService.find_one(rate_id)


@router.patch("/{rate_id}", response_model=JobRateResponse)
async def update_job_rate(
    rate_id: int,
    dto: JobRateUpdateDto,
    current_user: TokenData = Depends(require_any_role),
):
    """Update job rate."""
    return await JobRateService.update(rate_id, dto)


@router.delete("/{rate_id}")
@skip_interceptor
async def delete_job_rate(
    rate_id: int,
    current_user: TokenData = Depends(require_any_role),
):
    """Soft delete job rate."""
    await JobRateService.remove(rate_id)
    return {"message": "Job rate deleted successfully"}
