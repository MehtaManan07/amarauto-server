"""
Party DTOs.
"""

from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class PartyCreateDto(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    email: Optional[str] = Field(None, max_length=255)
    state: Optional[str] = Field(None, max_length=100)
    party_type: Optional[str] = Field(None, max_length=100)
    address_line_1: Optional[str] = Field(None, max_length=500)
    address_line_2: Optional[str] = Field(None, max_length=500)
    address_line_3: Optional[str] = Field(None, max_length=500)
    address_line_4: Optional[str] = Field(None, max_length=500)
    address_line_5: Optional[str] = Field(None, max_length=500)
    pin_code: Optional[str] = Field(None, max_length=20)
    phone: Optional[str] = Field(None, max_length=50)
    fax: Optional[str] = Field(None, max_length=50)
    contact_person: Optional[str] = Field(None, max_length=255)
    mobile: Optional[str] = Field(None, max_length=50)
    gstin: Optional[str] = Field(None, max_length=50)

    class Config:
        from_attributes = True


class PartyUpdateDto(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    email: Optional[str] = Field(None, max_length=255)
    state: Optional[str] = Field(None, max_length=100)
    party_type: Optional[str] = Field(None, max_length=100)
    address_line_1: Optional[str] = Field(None, max_length=500)
    address_line_2: Optional[str] = Field(None, max_length=500)
    address_line_3: Optional[str] = Field(None, max_length=500)
    address_line_4: Optional[str] = Field(None, max_length=500)
    address_line_5: Optional[str] = Field(None, max_length=500)
    pin_code: Optional[str] = Field(None, max_length=20)
    phone: Optional[str] = Field(None, max_length=50)
    fax: Optional[str] = Field(None, max_length=50)
    contact_person: Optional[str] = Field(None, max_length=255)
    mobile: Optional[str] = Field(None, max_length=50)
    gstin: Optional[str] = Field(None, max_length=50)

    class Config:
        from_attributes = True


class PartyResponse(BaseModel):
    id: int
    name: str
    email: Optional[str] = None
    state: Optional[str] = None
    party_type: Optional[str] = None
    address_line_1: Optional[str] = None
    address_line_2: Optional[str] = None
    address_line_3: Optional[str] = None
    address_line_4: Optional[str] = None
    address_line_5: Optional[str] = None
    pin_code: Optional[str] = None
    phone: Optional[str] = None
    fax: Optional[str] = None
    contact_person: Optional[str] = None
    mobile: Optional[str] = None
    gstin: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    deleted_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class PartyPaginatedResponse(BaseModel):
    """Paginated response for parties list."""

    items: list[PartyResponse]
    total: int
    page: int
    page_size: int
    total_pages: int
    has_more: bool

    class Config:
        from_attributes = True


class PartyFieldOptionsResponse(BaseModel):
    """Unique values for state, party_type dropdowns."""

    state: Optional[list[str]] = None
    party_type: Optional[list[str]] = None

    class Config:
        from_attributes = True
