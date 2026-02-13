"""
Production schemas - stage completion and inventory responses.
"""

from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime
from decimal import Decimal


class StageCompletionDto(BaseModel):
    """Request to complete a production stage."""

    product_id: int
    variant: Optional[str] = None
    stage_number: int = Field(..., ge=1, description="Which stage completing")
    quantity: Decimal = Field(..., gt=0, description="How many units completing")


class MaterialDeduction(BaseModel):
    """One material deducted during stage completion."""

    raw_material_id: int
    raw_material_name: str
    qty_deducted: Decimal
    remaining_stock: Decimal


class StageInventoryResponse(BaseModel):
    """Stage inventory row with product info."""

    id: int
    product_id: int
    product_part_no: Optional[str] = None
    product_name: Optional[str] = None
    variant: Optional[str] = None
    stage_number: int
    quantity: Decimal
    created_at: datetime
    updated_at: datetime


class StageCompletionResponse(BaseModel):
    """Response after completing a stage."""

    stage_inventory: StageInventoryResponse
    materials_deducted: List[MaterialDeduction] = []


class MaterialRequirement(BaseModel):
    """Material needed for a stage (preview)."""

    raw_material_id: int
    raw_material_name: str
    unit_type: str
    needed_qty: Decimal
    current_stock: Decimal
    shortage: Decimal
    status: str  # "ok" | "low"


class MaterialsPreviewResponse(BaseModel):
    """Preview of materials needed for stage completion."""

    product_part_no: str
    product_name: str
    variant: Optional[str] = None
    stage_number: int
    quantity: Decimal
    materials: List[MaterialRequirement]
    previous_stage_qty: Optional[Decimal] = None  # If stage > 1
