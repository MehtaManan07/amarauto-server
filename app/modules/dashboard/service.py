"""Dashboard service - counts and chart data."""

import time
from datetime import date, timedelta
from decimal import Decimal
from typing import Optional
from sqlalchemy import select, func, and_
from sqlalchemy.orm import Session

from app.core.db.engine import run_db
from app.modules.products.models import Product
from app.modules.raw_materials.models import RawMaterial
from app.modules.parties.models import Party
from app.modules.work_logs.models import WorkLog
from app.modules.production.models import Batch, BATCH_OPEN, BATCH_IN_PROGRESS, BATCH_DONE
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
            month_start = today.replace(day=1).isoformat()

            # Single query: all counts + production KPIs via scalar subqueries — one round-trip
            row = db.execute(
                select(
                    select(func.count())
                    .where(Product.deleted_at.is_(None))
                    .correlate(None)
                    .scalar_subquery()
                    .label("total_products"),

                    select(func.count())
                    .where(Product.deleted_at.is_(None), Product.is_active.is_(True))
                    .correlate(None)
                    .scalar_subquery()
                    .label("active_products"),

                    select(func.count())
                    .where(RawMaterial.deleted_at.is_(None))
                    .correlate(None)
                    .scalar_subquery()
                    .label("raw_materials_count"),

                    select(func.count())
                    .where(
                        RawMaterial.deleted_at.is_(None),
                        RawMaterial.min_stock_req.isnot(None),
                        RawMaterial.stock_qty < RawMaterial.min_stock_req,
                    )
                    .correlate(None)
                    .scalar_subquery()
                    .label("low_stock_count"),

                    select(func.count())
                    .where(Party.deleted_at.is_(None))
                    .correlate(None)
                    .scalar_subquery()
                    .label("parties_count"),

                    select(func.count())
                    .where(WorkLog.work_date == today)
                    .correlate(None)
                    .scalar_subquery()
                    .label("work_logs_today"),

                    select(func.count())
                    .where(
                        WorkLog.work_date >= week_start,
                        WorkLog.work_date <= today,
                    )
                    .correlate(None)
                    .scalar_subquery()
                    .label("work_logs_this_week"),

                    # Production KPIs
                    select(func.count())
                    .where(
                        Batch.deleted_at.is_(None),
                        Batch.status.in_([BATCH_OPEN, BATCH_IN_PROGRESS]),
                    )
                    .correlate(None)
                    .scalar_subquery()
                    .label("active_batches"),

                    func.coalesce(
                        select(func.sum(Batch.quantity))
                        .where(
                            Batch.deleted_at.is_(None),
                            Batch.status.in_([BATCH_OPEN, BATCH_IN_PROGRESS]),
                        )
                        .correlate(None)
                        .scalar_subquery(),
                        0,
                    ).label("units_on_floor"),

                    select(func.count())
                    .where(
                        Batch.deleted_at.is_(None),
                        Batch.status == BATCH_DONE,
                        Batch.completed_at >= month_start,
                    )
                    .correlate(None)
                    .scalar_subquery()
                    .label("completed_batches_month"),

                    func.coalesce(
                        select(func.sum(Batch.quantity))
                        .where(
                            Batch.deleted_at.is_(None),
                            Batch.status == BATCH_DONE,
                            Batch.completed_at >= month_start,
                        )
                        .correlate(None)
                        .scalar_subquery(),
                        0,
                    ).label("completed_units_month"),
                )
            ).one()

            return DashboardStatsResponse(
                total_products=row.total_products or 0,
                active_products=row.active_products or 0,
                raw_materials_count=row.raw_materials_count or 0,
                low_stock_count=row.low_stock_count or 0,
                parties_count=row.parties_count or 0,
                work_logs_today=row.work_logs_today or 0,
                work_logs_this_week=row.work_logs_this_week or 0,
                active_batches=row.active_batches or 0,
                units_on_floor=Decimal(str(row.units_on_floor or 0)),
                completed_batches_month=row.completed_batches_month or 0,
                completed_units_month=Decimal(str(row.completed_units_month or 0)),
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
