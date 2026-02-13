"""
Products router. CRUD + get BOM. List supports powerful search.
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, Query

from app.core.response_interceptor import skip_interceptor
from app.modules.users.auth import TokenData, require_any_role
from .service import ProductService
from .schemas import (
    ProductCreateDto,
    ProductUpdateDto,
    ProductResponse,
    ProductDetailResponse,
    ProductPaginatedResponse,
    ProductFieldOptionsResponse,
    BOMLineResponse,
    BulkCreateResponse,
)

router = APIRouter(prefix="/products", tags=["products"])


@router.post("", response_model=ProductResponse)
async def create_product(
    dto: ProductCreateDto,
    current_user: TokenData = Depends(require_any_role),
):
    """Add a product."""
    return await ProductService.create(dto)


@router.post("/bulk", response_model=BulkCreateResponse)
async def bulk_create_products(
    items: List[ProductCreateDto],
    current_user: TokenData = Depends(require_any_role),
):
    """Bulk add products. Duplicate part_no is skipped. Returns counts and one detail per item."""
    return await ProductService.bulk_create(items)


@router.get("", response_model=ProductPaginatedResponse)
async def list_products(
    search: Optional[str] = Query(None, description="Search across name, category, group, part_no, model_name, unit_of_measure (words AND'd)"),
    page: int = Query(1, ge=1, description="Page number (1-indexed)"),
    page_size: int = Query(25, ge=1, le=1000, description="Items per page (max 1000)"),
    current_user: TokenData = Depends(require_any_role),
):
    """List products with pagination. Optional search. Returns items, total, page, page_size, total_pages, has_more."""
    return await ProductService.find_all_paginated(
        page=page,
        page_size=page_size,
        search=search,
    )


@router.get("/field-options", response_model=ProductFieldOptionsResponse)
async def get_product_field_options(
    fields: Optional[str] = Query(
        None,
        description="Comma-separated field names: category, group, unit_of_measure. Omit for all.",
    ),
    current_user: TokenData = Depends(require_any_role),
):
    """Unique values for selectable fields. Frontend can show dropdowns; users can still enter new values."""
    field_list = [f.strip() for f in fields.split(",")] if fields else None
    data = await ProductService.get_field_options(fields=field_list)
    return ProductFieldOptionsResponse(**data)


@router.get("/{product_id}/bom", response_model=List[BOMLineResponse])
async def get_product_bom(
    product_id: int,
    variant: Optional[str] = Query(None, description="BOM variant e.g. colour"),
    current_user: TokenData = Depends(require_any_role),
):
    """Get BOM for product. Returns empty list until BOM module is implemented."""
    return await ProductService.get_bom(product_id, variant=variant)


@router.get("/{product_id}", response_model=ProductDetailResponse)
async def get_product(
    product_id: int,
    current_user: TokenData = Depends(require_any_role),
):
    """Get product by id (with BOM; BOM empty until BOM module exists)."""
    return await ProductService.find_one_with_bom(product_id)


@router.patch("/{product_id}", response_model=ProductResponse)
async def update_product(
    product_id: int,
    dto: ProductUpdateDto,
    current_user: TokenData = Depends(require_any_role),
):
    """Update product."""
    return await ProductService.update(product_id, dto)


@router.delete("/{product_id}")
@skip_interceptor
async def delete_product(
    product_id: int,
    current_user: TokenData = Depends(require_any_role),
):
    """Soft delete product."""
    await ProductService.remove(product_id)
    return {"message": "Product deleted successfully"}
