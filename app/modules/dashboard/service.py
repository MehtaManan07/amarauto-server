"""Dashboard service - counts only, no full data."""

from sqlalchemy import select, func
from sqlalchemy.orm import Session

from app.core.db.engine import run_db
from app.modules.products.models import Product
from app.modules.raw_materials.models import RawMaterial
from app.modules.dashboard.schemas import DashboardStatsResponse


class DashboardService:
    @staticmethod
    async def get_stats() -> DashboardStatsResponse:
        """Return counts for dashboard cards. No full data fetched."""

        def _get_stats(db: Session) -> DashboardStatsResponse:
            total_products = db.execute(
                select(func.count()).select_from(Product).where(Product.deleted_at.is_(None))
            ).scalar()
            total_products_count = total_products or 0

            active_products = db.execute(
                select(func.count()).select_from(Product).where(
                    Product.deleted_at.is_(None),
                    Product.is_active.is_(True),
                )
            ).scalar()
            active_products_count = active_products or 0

            raw_materials = db.execute(
                select(func.count()).select_from(RawMaterial).where(RawMaterial.deleted_at.is_(None))
            ).scalar()
            raw_materials_count = raw_materials or 0

            low_stock = db.execute(
                select(func.count()).select_from(RawMaterial).where(
                    RawMaterial.deleted_at.is_(None),
                    RawMaterial.min_stock_req.isnot(None),
                    RawMaterial.stock_qty < RawMaterial.min_stock_req,
                )
            ).scalar()
            low_stock_count = low_stock or 0

            return DashboardStatsResponse(
                total_products=total_products_count,
                active_products=active_products_count,
                raw_materials_count=raw_materials_count,
                low_stock_count=low_stock_count,
            )

        return await run_db(_get_stats)
