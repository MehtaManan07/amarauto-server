"""
Parties router. CRUD + field options. List supports search and filters.
"""

from typing import Optional
from fastapi import APIRouter, Depends, Query

from app.core.response_interceptor import skip_interceptor
from app.modules.users.auth import get_current_user, TokenData, require_any_role
from .service import PartyService
from .schemas import (
    PartyCreateDto,
    PartyUpdateDto,
    PartyResponse,
    PartyPaginatedResponse,
    PartyFieldOptionsResponse,
)

router = APIRouter(prefix="/parties", tags=["parties"])


@router.post("", response_model=PartyResponse)
async def create_party(
    dto: PartyCreateDto,
    current_user: TokenData = Depends(require_any_role),
):
    """Add a party (customer/debtor)."""
    return await PartyService.create(dto)


@router.get("", response_model=PartyPaginatedResponse)
async def list_parties(
    search: Optional[str] = Query(
        None,
        description="Search across name, email, state, contact_person, mobile, gstin (words AND'd)",
    ),
    state: Optional[str] = Query(None, description="Filter by state"),
    party_type: Optional[str] = Query(None, description="Filter by party_type"),
    page: int = Query(1, ge=1, description="Page number (1-indexed)"),
    page_size: int = Query(25, ge=1, le=1000, description="Items per page (max 1000)"),
    current_user: TokenData = Depends(require_any_role),
):
    """List parties with pagination. Optional search and filters."""
    return await PartyService.find_all_paginated(
        page=page,
        page_size=page_size,
        search=search,
        state=state,
        party_type=party_type,
    )


@router.get("/field-options", response_model=PartyFieldOptionsResponse)
async def get_field_options(
    fields: Optional[str] = Query(
        None,
        description="Comma-separated field names: state, party_type. Omit for all.",
    ),
    current_user: TokenData = Depends(require_any_role),
):
    """Unique values for state, party_type. Frontend can show dropdowns; users can still enter new values."""
    field_list = [f.strip() for f in fields.split(",")] if fields else None
    data = await PartyService.get_field_options(fields=field_list)
    return PartyFieldOptionsResponse(**data)


@router.get("/{party_id}", response_model=PartyResponse)
async def get_party(
    party_id: int,
    current_user: TokenData = Depends(require_any_role),
):
    """Get party by id."""
    return await PartyService.find_one(party_id)


@router.patch("/{party_id}", response_model=PartyResponse)
async def update_party(
    party_id: int,
    dto: PartyUpdateDto,
    current_user: TokenData = Depends(require_any_role),
):
    """Update party."""
    return await PartyService.update(party_id, dto)


@router.delete("/{party_id}")
@skip_interceptor
async def delete_party(
    party_id: int,
    current_user: TokenData = Depends(require_any_role),
):
    """Soft delete party."""
    await PartyService.remove(party_id)
    return {"message": "Party deleted successfully"}
