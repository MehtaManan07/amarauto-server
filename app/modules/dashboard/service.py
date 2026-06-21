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
from app.modules.production.models import Batch, BatchCompletion, BATCH_OPEN, BATCH_IN_PROGRESS, BATCH_DONE
from app.modules.production.models import BatchMovement, BatchReject
from app.modules.stages.models import Stage
from app.modules.dashboard.schemas import (
    DashboardStatsResponse,
    LowStockItem,
    FloorStageItem,
    DailyCompletion,
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

            # Low stock materials (top 8, below min_stock_req).
            low_stock_rows = db.execute(
                select(RawMaterial)
                .where(
                    RawMaterial.deleted_at.is_(None),
                    RawMaterial.min_stock_req.isnot(None),
                    RawMaterial.stock_qty < RawMaterial.min_stock_req,
                )
                .order_by(RawMaterial.stock_qty)
                .limit(8)
            ).scalars().all()
            low_stock_materials = [
                LowStockItem(id=r.id, name=r.name, stock_qty=r.stock_qty or Decimal("0"),
                             min_stock_req=r.min_stock_req, unit_type=r.unit_type)
                for r in low_stock_rows
            ]

            # Floor by stage: batch count + unit count per active stage.
            stages = db.execute(
                select(Stage).where(Stage.deleted_at.is_(None)).order_by(Stage.sequence)
            ).scalars().all()
            active_batch_ids = [
                bid for (bid,) in db.execute(
                    select(Batch.id).where(
                        Batch.deleted_at.is_(None),
                        Batch.status.in_([BATCH_OPEN, BATCH_IN_PROGRESS]),
                    )
                ).all()
            ]
            # Derive current stage for each active batch via WIP (moved_in - moved_out - rejected - completed).
            from collections import defaultdict
            stage_seq = {s.id: s.sequence for s in stages}
            wip: dict = {bid: defaultdict(Decimal) for bid in active_batch_ids}
            if active_batch_ids:
                for bid, sid, qty in db.execute(
                    select(BatchMovement.batch_id, BatchMovement.to_stage_id, func.sum(BatchMovement.quantity))
                    .where(BatchMovement.batch_id.in_(active_batch_ids), BatchMovement.deleted_at.is_(None))
                    .group_by(BatchMovement.batch_id, BatchMovement.to_stage_id)
                ).all():
                    wip[bid][sid] += qty or Decimal("0")
                for bid, sid, qty in db.execute(
                    select(BatchMovement.batch_id, BatchMovement.from_stage_id, func.sum(BatchMovement.quantity))
                    .where(BatchMovement.batch_id.in_(active_batch_ids), BatchMovement.deleted_at.is_(None),
                           BatchMovement.from_stage_id.isnot(None))
                    .group_by(BatchMovement.batch_id, BatchMovement.from_stage_id)
                ).all():
                    wip[bid][sid] -= qty or Decimal("0")
                for bid, sid, qty in db.execute(
                    select(BatchReject.batch_id, BatchReject.stage_id, func.sum(BatchReject.quantity))
                    .where(BatchReject.batch_id.in_(active_batch_ids), BatchReject.deleted_at.is_(None))
                    .group_by(BatchReject.batch_id, BatchReject.stage_id)
                ).all():
                    wip[bid][sid] -= qty or Decimal("0")
                from app.modules.production.models import BatchCompletion as BC
                for bid, sid, qty in db.execute(
                    select(BC.batch_id, BC.stage_id, func.sum(BC.quantity))
                    .where(BC.batch_id.in_(active_batch_ids), BC.deleted_at.is_(None))
                    .group_by(BC.batch_id, BC.stage_id)
                ).all():
                    wip[bid][sid] -= qty or Decimal("0")
            # Aggregate: for each batch, sum units waiting per stage.
            stage_batches: dict = defaultdict(int)
            stage_units: dict = defaultdict(Decimal)
            for bid, stage_wip in wip.items():
                for sid, waiting in stage_wip.items():
                    if waiting > 0 and sid in stage_seq:
                        stage_batches[sid] += 1
                        stage_units[sid] += waiting
            floor_by_stage = [
                FloorStageItem(stage_id=s.id, stage_name=s.name, sequence=s.sequence,
                               batch_count=stage_batches.get(s.id, 0),
                               unit_count=stage_units.get(s.id, Decimal("0")))
                for s in stages
            ]

            # Daily completions — last 30 days.
            thirty_ago = (today - timedelta(days=29)).isoformat()
            comp_rows = db.execute(
                select(BatchCompletion.created_at, BatchCompletion.quantity)
                .where(
                    BatchCompletion.deleted_at.is_(None),
                    BatchCompletion.created_at >= thirty_ago,
                )
            ).all()
            daily: dict = defaultdict(Decimal)
            for created_at, qty in comp_rows:
                if created_at:
                    daily[created_at.date().isoformat()] += qty or Decimal("0")
            all_dates = [(today - timedelta(days=i)).isoformat() for i in range(29, -1, -1)]
            daily_completions = [
                DailyCompletion(date=d, units=daily.get(d, Decimal("0")))
                for d in all_dates
            ]

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
                low_stock_materials=low_stock_materials,
                floor_by_stage=floor_by_stage,
                daily_completions=daily_completions,
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
