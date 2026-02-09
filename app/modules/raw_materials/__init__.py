"""Raw materials module - inventory and stock for raw materials."""

from app.modules.raw_materials.models import RawMaterial
from app.modules.raw_materials.router import router

__all__ = ["RawMaterial", "router"]
