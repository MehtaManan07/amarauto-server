"""Dashboard service — concurrent sub-queries, single-response for the frontend."""

import asyncio
import time
from collections import defaultdict
from datetime import date, timedelta
from decimal import Decimal
from typing import Dict, List, Optional

from sqlalchemy import select, func, union_all
from sqlalchemy.orm import Session

from app.core.db.engine import run_db
from app.modules.products.models import Product
from app.modules.raw_materials.models import RawMaterial
from app.modules.parties.models import Party
from app.modules.work_logs.models import WorkLog
from app.modules.production.models import (
    Batch, BatchMovement, BatchReject, BatchCompletion,
    BATCH_OPEN, BATCH_IN_PROGRESS, BATCH_DONE,
)
from app.modules.stages.models import Stage
from app.modules.dashboard.schemas import (
    DashboardStatsResponse,
    LowStockItem,
    FloorStageItem,
    DailyCompletion,
    ProductionTrendItem,
    ProductionTrendResponse,
)

# 60s in-memory cache — dashboard data is derived/read-only and updating
# every minute is more than sufficient.
_stats_cache: Optional[DashboardStatsResponse] = None
_stats_cache_time: float = 0.0
_STATS_TTL: float = 60.0


# ── Sub-query helpers (each runs in its own thread / DB connection) ────────────

def _build_counts(db: Session):
    """All scalar KPI counts in one round-trip."""
    today = date.today()
    week_start = today - timedelta(days=7)
    month_start = today.replace(day=1).isoformat()
    return db.execute(select(
        select(func.count()).where(Product.deleted_at.is_(None)).correlate(None).scalar_subquery().label("total_products"),
        select(func.count()).where(Product.deleted_at.is_(None), Product.is_active.is_(True)).correlate(None).scalar_subquery().label("active_products"),
        select(func.count()).where(RawMaterial.deleted_at.is_(None)).correlate(None).scalar_subquery().label("raw_materials_count"),
        select(func.count()).where(RawMaterial.deleted_at.is_(None), RawMaterial.min_stock_req.isnot(None), RawMaterial.stock_qty < RawMaterial.min_stock_req).correlate(None).scalar_subquery().label("low_stock_count"),
        select(func.count()).where(Party.deleted_at.is_(None)).correlate(None).scalar_subquery().label("parties_count"),
        select(func.count()).where(WorkLog.work_date == today).correlate(None).scalar_subquery().label("work_logs_today"),
        select(func.count()).where(WorkLog.work_date >= week_start, WorkLog.work_date <= today).correlate(None).scalar_subquery().label("work_logs_this_week"),
        select(func.count()).where(Batch.deleted_at.is_(None), Batch.status.in_([BATCH_OPEN, BATCH_IN_PROGRESS])).correlate(None).scalar_subquery().label("active_batches"),
        func.coalesce(select(func.sum(Batch.quantity)).where(Batch.deleted_at.is_(None), Batch.status.in_([BATCH_OPEN, BATCH_IN_PROGRESS])).correlate(None).scalar_subquery(), 0).label("units_on_floor"),
        select(func.count()).where(Batch.deleted_at.is_(None), Batch.status == BATCH_DONE, Batch.completed_at >= month_start).correlate(None).scalar_subquery().label("completed_batches_month"),
        func.coalesce(select(func.sum(Batch.quantity)).where(Batch.deleted_at.is_(None), Batch.status == BATCH_DONE, Batch.completed_at >= month_start).correlate(None).scalar_subquery(), 0).label("completed_units_month"),
    )).one()


def _build_low_stock(db: Session) -> List[LowStockItem]:
    rows = db.execute(
        select(RawMaterial)
        .where(RawMaterial.deleted_at.is_(None), RawMaterial.min_stock_req.isnot(None),
               RawMaterial.stock_qty < RawMaterial.min_stock_req)
        .order_by(RawMaterial.stock_qty).limit(8)
    ).scalars().all()
    return [
        LowStockItem(id=r.id, name=r.name, stock_qty=r.stock_qty or Decimal("0"),
                     min_stock_req=r.min_stock_req, unit_type=r.unit_type)
        for r in rows
    ]


def _build_stages(db: Session) -> List[Stage]:
    return list(db.execute(
        select(Stage).where(Stage.deleted_at.is_(None)).order_by(Stage.sequence)
    ).scalars().all())


def _build_wip(db: Session):
    """Per-(batch, stage) net WIP via a single UNION ALL — no pre-fetch of active batch IDs."""
    active = [BATCH_OPEN, BATCH_IN_PROGRESS]
    m_in = (
        select(BatchMovement.batch_id, BatchMovement.to_stage_id.label("stage_id"),
               BatchMovement.quantity.label("delta"))
        .join(Batch, BatchMovement.batch_id == Batch.id)
        .where(Batch.status.in_(active), Batch.deleted_at.is_(None), BatchMovement.deleted_at.is_(None))
    )
    m_out = (
        select(BatchMovement.batch_id, BatchMovement.from_stage_id.label("stage_id"),
               (-BatchMovement.quantity).label("delta"))
        .join(Batch, BatchMovement.batch_id == Batch.id)
        .where(Batch.status.in_(active), Batch.deleted_at.is_(None), BatchMovement.deleted_at.is_(None),
               BatchMovement.from_stage_id.isnot(None))
    )
    rej = (
        select(BatchReject.batch_id, BatchReject.stage_id, (-BatchReject.quantity).label("delta"))
        .join(Batch, BatchReject.batch_id == Batch.id)
        .where(Batch.status.in_(active), Batch.deleted_at.is_(None), BatchReject.deleted_at.is_(None))
    )
    comp = (
        select(BatchCompletion.batch_id, BatchCompletion.stage_id, (-BatchCompletion.quantity).label("delta"))
        .join(Batch, BatchCompletion.batch_id == Batch.id)
        .where(Batch.status.in_(active), Batch.deleted_at.is_(None), BatchCompletion.deleted_at.is_(None))
    )
    sub = union_all(m_in, m_out, rej, comp).subquery()
    return db.execute(
        select(sub.c.batch_id, sub.c.stage_id, func.sum(sub.c.delta).label("net"))
        .group_by(sub.c.batch_id, sub.c.stage_id)
        .having(func.sum(sub.c.delta) > 0)
    ).all()


def _build_daily(db: Session) -> List[DailyCompletion]:
    today = date.today()
    thirty_ago = (today - timedelta(days=29)).isoformat()
    rows = db.execute(
        select(BatchCompletion.created_at, BatchCompletion.quantity)
        .where(BatchCompletion.deleted_at.is_(None), BatchCompletion.created_at >= thirty_ago)
    ).all()
    daily: Dict[str, Decimal] = defaultdict(Decimal)
    for created_at, qty in rows:
        if created_at:
            daily[created_at.date().isoformat()] += qty or Decimal("0")
    return [
        DailyCompletion(date=d, units=daily.get(d, Decimal("0")))
        for d in ((today - timedelta(days=i)).isoformat() for i in range(29, -1, -1))
    ]


# ── Public service ─────────────────────────────────────────────────────────────

class DashboardService:
    @staticmethod
    async def get_stats() -> DashboardStatsResponse:
        """Return all dashboard data in one response.

        Runs 5 independent DB queries concurrently via asyncio.gather — each
        gets its own connection from the pool. Wall-clock ≈ slowest single
        query (~600ms Mumbai→Ohio) instead of sum of all queries (~5s). The
        60s in-memory cache then makes subsequent loads instant.
        """
        global _stats_cache, _stats_cache_time

        now = time.monotonic()
        if _stats_cache is not None and (now - _stats_cache_time) < _STATS_TTL:
            return _stats_cache

        counts, low_stock, stages, wip_rows, daily = await asyncio.gather(
            run_db(_build_counts),
            run_db(_build_low_stock),
            run_db(_build_stages),
            run_db(_build_wip),
            run_db(_build_daily),
        )

        # Assemble floor_by_stage: sum waiting units per stage across all active batches.
        stage_batches: Dict[int, int] = defaultdict(int)
        stage_units: Dict[int, Decimal] = defaultdict(Decimal)
        for _bid, stage_id, net in wip_rows:
            if stage_id is not None:
                stage_batches[stage_id] += 1
                stage_units[stage_id] += net or Decimal("0")
        floor_by_stage = [
            FloorStageItem(stage_id=s.id, stage_name=s.name, sequence=s.sequence,
                           batch_count=stage_batches.get(s.id, 0),
                           unit_count=stage_units.get(s.id, Decimal("0")))
            for s in stages
        ]

        result = DashboardStatsResponse(
            total_products=counts.total_products or 0,
            active_products=counts.active_products or 0,
            raw_materials_count=counts.raw_materials_count or 0,
            low_stock_count=counts.low_stock_count or 0,
            parties_count=counts.parties_count or 0,
            work_logs_today=counts.work_logs_today or 0,
            work_logs_this_week=counts.work_logs_this_week or 0,
            active_batches=counts.active_batches or 0,
            units_on_floor=Decimal(str(counts.units_on_floor or 0)),
            completed_batches_month=counts.completed_batches_month or 0,
            completed_units_month=Decimal(str(counts.completed_units_month or 0)),
            low_stock_materials=low_stock,
            floor_by_stage=floor_by_stage,
            daily_completions=daily,
        )
        _stats_cache, _stats_cache_time = result, now
        return result

    @staticmethod
    async def get_production_trend(days: int = 7) -> ProductionTrendResponse:
        """Return daily work-log aggregates for last N days (kept for backward compat)."""

        def _get_trend(db: Session) -> ProductionTrendResponse:
            end_date = date.today()
            start_date = end_date - timedelta(days=days - 1)
            all_dates = [(start_date + timedelta(days=i)).isoformat() for i in range(days)]
            stmt = (
                select(WorkLog.work_date, func.count(WorkLog.id).label("work_log_count"),
                       func.coalesce(func.sum(WorkLog.total_amount), 0).label("total_amount"))
                .where(WorkLog.work_date >= start_date, WorkLog.work_date <= end_date)
                .group_by(WorkLog.work_date)
            )
            by_date = {r.work_date.isoformat(): r for r in db.execute(stmt).all()}
            items = [
                ProductionTrendItem(
                    date=d,
                    work_log_count=by_date[d].work_log_count if d in by_date else 0,
                    total_amount=Decimal(str(by_date[d].total_amount)) if d in by_date else Decimal("0"),
                )
                for d in all_dates
            ]
            return ProductionTrendResponse(items=items)

        return await run_db(_get_trend)
