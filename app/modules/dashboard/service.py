"""Dashboard service - counts and chart data."""

import time
from datetime import date, timedelta
from decimal import Decimal
from typing import Optional
from sqlalchemy import select, func, case, and_
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

# Simple in-memory TTL cache for dashboard stats
_stats_cache: Optional[DashboardStatsResponse] = None
_stats_cache_time: float = 0
_STATS_TTL: float = 60  # seconds


class DashboardService:
    @staticmethod
    async def get_stats() -> DashboardStatsResponse:
        """Return counts for dashboard cards. Cached for 60s."""
        global _stats_cache, _stats_cache_time

        now = time.monotonic()
        if _stats_cache is not None and (now - _stats_cache_time) < _STATS_TTL:
            return _stats_cache

        def _get_stats(db: Session) -> DashboardStatsResponse:
            today = date.today()
            week_start = today - timedelta(days=7)

            # Single query: all 7 counts in one DB round-trip
            row = db.execute(
                select(
                    # Products
                    func.count(case(
                        (Product.deleted_at.is_(None), Product.id),
                    )).label("total_products"),
                    func.count(case(
                        (and_(Product.deleted_at.is_(None), Product.is_active.is_(True)), Product.id),
                    )).label("active_products"),
                ).select_from(Product)
            ).one()

            rm_row = db.execute(
                select(
                    func.count(case(
                        (RawMaterial.deleted_at.is_(None), RawMaterial.id),
                    )).label("raw_materials_count"),
                    func.count(case(
                        (and_(
                            RawMaterial.deleted_at.is_(None),
                            RawMaterial.min_stock_req.isnot(None),
                            RawMaterial.stock_qty < RawMaterial.min_stock_req,
                        ), RawMaterial.id),
                    )).label("low_stock_count"),
                ).select_from(RawMaterial)
            ).one()

            party_count = db.execute(
                select(func.count()).select_from(Party).where(Party.deleted_at.is_(None))
            ).scalar() or 0

            wl_row = db.execute(
                select(
                    func.count(case(
                        (WorkLog.work_date == today, WorkLog.id),
                    )).label("work_logs_today"),
                    func.count(case(
                        (and_(WorkLog.work_date >= week_start, WorkLog.work_date <= today), WorkLog.id),
                    )).label("work_logs_this_week"),
                ).select_from(WorkLog)
            ).one()

            return DashboardStatsResponse(
                total_products=row.total_products or 0,
                active_products=row.active_products or 0,
                raw_materials_count=rm_row.raw_materials_count or 0,
                low_stock_count=rm_row.low_stock_count or 0,
                parties_count=party_count,
                work_logs_today=wl_row.work_logs_today or 0,
                work_logs_this_week=wl_row.work_logs_this_week or 0,
            )

        result = await run_db(_get_stats)
        _stats_cache = result
        _stats_cache_time = time.monotonic()
        return result

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
