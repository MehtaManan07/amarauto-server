"""Inventory log service - create and fetch logs."""

from typing import List
from sqlalchemy import select, func
from sqlalchemy.orm import Session
from decimal import Decimal

from app.core.db.engine import run_db
from app.core.pagination import build_paginated_response
from app.modules.inventory_logs.models import InventoryLog, LogType
from app.modules.inventory_logs.schemas import InventoryLogResponse


class InventoryLogService:
    @staticmethod
    async def create_log(
        raw_material_id: int,
        log_type: LogType,
        quantity_delta: Decimal,
        previous_qty: Decimal,
        new_qty: Decimal,
        user_id: int | None = None,
        notes: str | None = None,
    ) -> InventoryLogResponse:
        """Create an inventory log entry."""

        def _create(db: Session) -> InventoryLogResponse:
            log = InventoryLog(
                raw_material_id=raw_material_id,
                user_id=user_id,
                type=log_type.value,
                quantity_delta=quantity_delta,
                previous_qty=previous_qty,
                new_qty=new_qty,
                notes=notes,
            )
            db.add(log)
            db.flush()
            db.refresh(log)
            return InventoryLogResponse(
                id=log.id,
                raw_material_id=log.raw_material_id,
                user_id=log.user_id,
                type=log.type,
                quantity_delta=log.quantity_delta,
                previous_qty=log.previous_qty,
                new_qty=log.new_qty,
                notes=log.notes,
                created_at=log.created_at,
            )

        return await run_db(_create)

    @staticmethod
    async def get_logs_by_raw_material(
        raw_material_id: int,
        page: int = 1,
        page_size: int = 25,
    ) -> dict:
        """Get inventory logs for a raw material, newest first, with pagination."""

        def _get(db: Session) -> dict:
            base_query = (
                select(InventoryLog)
                .where(InventoryLog.raw_material_id == raw_material_id)
                .order_by(InventoryLog.created_at.desc())
            )

            total = db.execute(
                select(func.count()).select_from(base_query.subquery())
            ).scalar() or 0

            offset = (page - 1) * page_size
            rows = db.execute(base_query.offset(offset).limit(page_size)).scalars().all()
            items = [
                InventoryLogResponse(
                    id=r.id,
                    raw_material_id=r.raw_material_id,
                    user_id=r.user_id,
                    type=r.type,
                    quantity_delta=r.quantity_delta,
                    previous_qty=r.previous_qty,
                    new_qty=r.new_qty,
                    notes=r.notes,
                    created_at=r.created_at,
                )
                for r in rows
            ]
            return build_paginated_response(items, total, page, page_size)

        return await run_db(_get)
