"""Dashboard service - counts and chart data."""

from datetime import date, timedelta
from decimal import Decimal
from sqlalchemy import select, func
from sqlalchemy.orm import Session

from app.core.db.engine import run_db
from app.modules.products.models import Product
from app.modules.raw_materials.models import RawMaterial
from app.modules.parties.models import Party
from app.modules.work_logs.models import WorkLog
from app.modules.dashboard.schemas import (
    DashboardStatsResponse,
    ProductionTrendItem,
    ProductionTrendResponse,
)


class DashboardService:
    @staticmethod
    async def get_stats() -> DashboardStatsResponse:
        """Return counts for dashboard cards."""

        def _get_stats(db: Session) -> DashboardStatsResponse:
            today = date.today()
            week_start = today - timedelta(days=7)

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

            parties = db.execute(
                select(func.count()).select_from(Party).where(Party.deleted_at.is_(None))
            ).scalar()
            parties_count = parties or 0

            work_today = db.execute(
                select(func.count()).select_from(WorkLog).where(WorkLog.work_date == today)
            ).scalar()
            work_logs_today = work_today or 0

            work_week = db.execute(
                select(func.count()).select_from(WorkLog).where(
                    WorkLog.work_date >= week_start,
                    WorkLog.work_date <= today,
                )
            ).scalar()
            work_logs_this_week = work_week or 0

            return DashboardStatsResponse(
                total_products=total_products_count,
                active_products=active_products_count,
                raw_materials_count=raw_materials_count,
                low_stock_count=low_stock_count,
                parties_count=parties_count,
                work_logs_today=work_logs_today,
                work_logs_this_week=work_logs_this_week,
            )

        return await run_db(_get_stats)

    @staticmethod
    async def get_production_trend(days: int = 7) -> ProductionTrendResponse:
        """Return daily production aggregates for last N days."""

        def _get_trend(db: Session) -> ProductionTrendResponse:
            end_date = date.today()
            start_date = end_date - timedelta(days=days - 1)

            # Build list of all dates in range (include days with zero)
            all_dates = [
                (start_date + timedelta(days=i)).isoformat()
                for i in range((end_date - start_date).days + 1)
            ]

            # Query aggregated by work_date
            stmt = (
                select(
                    WorkLog.work_date,
                    func.count(WorkLog.id).label("work_log_count"),
                    func.coalesce(func.sum(WorkLog.total_amount), 0).label("total_amount"),
                )
                .where(
                    WorkLog.work_date >= start_date,
                    WorkLog.work_date <= end_date,
                )
                .group_by(WorkLog.work_date)
            )
            result = db.execute(stmt)
            rows = result.all()

            by_date = {r.work_date.isoformat(): r for r in rows}

            items = []
            for d in all_dates:
                if d in by_date:
                    r = by_date[d]
                    items.append(
                        ProductionTrendItem(
                            date=d,
                            work_log_count=r.work_log_count,
                            total_amount=Decimal(str(r.total_amount)),
                        )
                    )
                else:
                    items.append(
                        ProductionTrendItem(
                            date=d,
                            work_log_count=0,
                            total_amount=Decimal("0"),
                        )
                    )

            return ProductionTrendResponse(items=items)

        return await run_db(_get_trend)
