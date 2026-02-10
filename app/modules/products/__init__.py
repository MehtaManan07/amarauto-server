"""Products module - finished product catalog and BOM."""

from app.modules.products.models import Product
from app.modules.products.router import router

__all__ = ["Product", "router"]
