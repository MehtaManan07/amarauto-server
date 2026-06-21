"""
Raw materials service. find_all with powerful search; check_stock for low/below-min.
"""

from typing import Dict, List, Optional
from math import ceil
from sqlalchemy import select, func, or_, union_all, literal
from sqlalchemy.orm import Session
from datetime import datetime, date
from decimal import Decimal

from app.core.db.engine import run_db
from app.core.exceptions import ConflictError, NotFoundError
from app.core.pagination import paginate_query, build_paginated_response
from app.core.utils import search_words, normalize_unicode
from app.modules.raw_materials.models import RawMaterial
from app.modules.inventory_logs.models import InventoryLog, LogType
from app.modules.raw_materials.schemas import (
    RawMaterialCreateDto,
    RawMaterialUpdateDto,
    RawMaterialResponse,
    StockCheckResponse,
    BulkUploadResponse,
    BulkUploadItemResult,
    ConsumptionEventLine,
    ConsumptionResponse,
)


def _to_response(row: RawMaterial) -> RawMaterialResponse:
    return RawMaterialResponse(
        id=row.id,
        name=row.name,
        unit_type=row.unit_type,
        material_type=row.material_type,
        group=row.group,
        min_stock_req=row.min_stock_req,
        min_order_qty=row.min_order_qty,
        stock_qty=row.stock_qty,
        gst=row.gst,
        hsn=row.hsn,
        purchase_price=row.purchase_price,
        description=row.description,
        treat_as_consume=row.treat_as_consume,
        is_active=row.is_active,
        created_at=row.created_at,
        updated_at=row.updated_at,
        deleted_at=row.deleted_at,
    )


ALLOWED_FIELD_OPTIONS_FIELDS = ("unit_type", "material_type", "group")


class RawMaterialService:
    @staticmethod
    async def get_field_options(
        fields: Optional[List[str]] = None,
    ) -> Dict[str, List[str]]:
        """
        Return distinct non-null values for selectable fields (unit_type, material_type, group)
        from non-deleted raw materials. Used by frontend for dropdowns; users can still enter new values.
        """
        requested = (
            [f for f in fields if f in ALLOWED_FIELD_OPTIONS_FIELDS]
            if fields
            else list(ALLOWED_FIELD_OPTIONS_FIELDS)
        )
        if not requested:
            return {}

        def _get_options(db: Session) -> Dict[str, List[str]]:
            subqueries = [
                select(literal(field).label("field"), getattr(RawMaterial, field).label("value"))
                .where(RawMaterial.deleted_at.is_(None), getattr(RawMaterial, field).isnot(None))
                .distinct()
                for field in requested
            ]
            rows = db.execute(union_all(*subqueries)).all()
            out: Dict[str, List[str]] = {f: [] for f in requested}
            for field_name, value in rows:
                out[field_name].append(value)
            for field_name in out:
                out[field_name].sort()
            return out

        return await run_db(_get_options)

    @staticmethod
    async def create(dto: RawMaterialCreateDto) -> RawMaterialResponse:
        def _create(db: Session) -> RawMaterialResponse:
            existing = db.execute(
                select(RawMaterial).where(RawMaterial.name == dto.name, RawMaterial.deleted_at.is_(None))
            )
            if existing.scalars().first():
                raise ConflictError("Raw material already exists with this name")
            now = datetime.utcnow()
            row = RawMaterial(
                name=normalize_unicode(dto.name) or dto.name,
                unit_type=dto.unit_type,
                material_type=normalize_unicode(dto.material_type) if dto.material_type else dto.material_type,
                group=normalize_unicode(dto.group) if dto.group else dto.group,
                min_stock_req=dto.min_stock_req,
                min_order_qty=dto.min_order_qty,
                stock_qty=dto.stock_qty,
                gst=dto.gst,
                hsn=dto.hsn,
                purchase_price=dto.purchase_price,
                description=normalize_unicode(dto.description) if dto.description else dto.description,
                treat_as_consume=dto.treat_as_consume,
                is_active=dto.is_active,
                created_at=now,
                updated_at=now,
            )
            db.add(row)
            db.flush()
            return _to_response(row)
        return await run_db(_create)

    @staticmethod
    async def bulk_create(items: List[RawMaterialCreateDto]) -> BulkUploadResponse:
        """
        Bulk create raw materials. Each item is processed independently;
        conflicts and errors are captured per-item and don't fail the entire batch.
        """
        def _bulk_create(db: Session) -> BulkUploadResponse:
            results: List[BulkUploadItemResult] = []
            success_count = 0
            failure_count = 0

            # Single query to check all duplicates upfront
            all_names = [dto.name for dto in items]
            existing_names = set(
                db.execute(
                    select(RawMaterial.name).where(
                        RawMaterial.name.in_(all_names),
                        RawMaterial.deleted_at.is_(None),
                    )
                ).scalars().all()
            )

            now = datetime.utcnow()
            # Use indexed results so order is preserved after batch flush
            results = [None] * len(items)
            pending_rows: list[tuple[RawMaterial, int]] = []

            for i, dto in enumerate(items):
                try:
                    if dto.name in existing_names:
                        results[i] = BulkUploadItemResult(
                            name=dto.name,
                            success=False,
                            error="Material with this name already exists",
                            data=None,
                        )
                        failure_count += 1
                        continue

                    row = RawMaterial(
                        name=normalize_unicode(dto.name) or dto.name,
                        unit_type=dto.unit_type,
                        material_type=normalize_unicode(dto.material_type) if dto.material_type else dto.material_type,
                        group=normalize_unicode(dto.group) if dto.group else dto.group,
                        min_stock_req=dto.min_stock_req,
                        min_order_qty=dto.min_order_qty,
                        stock_qty=dto.stock_qty,
                        gst=dto.gst,
                        hsn=dto.hsn,
                        purchase_price=dto.purchase_price,
                        description=normalize_unicode(dto.description) if dto.description else dto.description,
                        treat_as_consume=dto.treat_as_consume,
                        is_active=dto.is_active,
                        created_at=now,
                        updated_at=now,
                    )
                    db.add(row)
                    pending_rows.append((row, i))
                    success_count += 1

                except Exception as e:
                    results[i] = BulkUploadItemResult(
                        name=dto.name,
                        success=False,
                        error=str(e),
                        data=None,
                    )
                    failure_count += 1

            # Single flush for all rows — one DB round-trip instead of N
            if pending_rows:
                db.flush()

            for row, idx in pending_rows:
                results[idx] = BulkUploadItemResult(
                    name=items[idx].name,
                    success=True,
                    error=None,
                    data=_to_response(row),
                )

            return BulkUploadResponse(
                total=len(items),
                success_count=success_count,
                failure_count=failure_count,
                results=results,
            )

        return await run_db(_bulk_create)

    @staticmethod
    async def find_all(search: Optional[str] = None) -> List[RawMaterialResponse]:
        """
        List non-deleted raw materials. Optional search: split into words;
        each word must match at least one of name, unit_type, material_type, group, description.
        """
        words = search_words(search)

        def _find_all(db: Session) -> List[RawMaterialResponse]:
            query = select(RawMaterial).where(RawMaterial.deleted_at.is_(None))
            for word in words:
                pattern = f"%{word}%"
                query = query.where(
                    or_(
                        RawMaterial.name.ilike(pattern),
                        RawMaterial.unit_type.ilike(pattern),
                        RawMaterial.material_type.ilike(pattern),
                        RawMaterial.group.ilike(pattern),
                        RawMaterial.description.ilike(pattern),
                    )
                )
            query = query.order_by(RawMaterial.created_at.desc())
            result = db.execute(query)
            rows = result.scalars().all()
            return [_to_response(r) for r in rows]
        return await run_db(_find_all)

    @staticmethod
    async def find_all_paginated(
        page: int = 1,
        page_size: int = 25,
        search: Optional[str] = None,
    ) -> dict:
        """
        Find all raw materials with pagination and optional search filter.
        """
        words = search_words(search)

        def _find_all_paginated(db: Session) -> dict:
            query = select(RawMaterial).where(RawMaterial.deleted_at.is_(None))
            for word in words:
                pattern = f"%{word}%"
                query = query.where(
                    or_(
                        RawMaterial.name.ilike(pattern),
                        RawMaterial.unit_type.ilike(pattern),
                        RawMaterial.material_type.ilike(pattern),
                        RawMaterial.group.ilike(pattern),
                        RawMaterial.description.ilike(pattern),
                    )
                )
            query = query.order_by(RawMaterial.created_at.desc())
            rows, total = paginate_query(db, query, page, page_size)
            items = [_to_response(r) for r in rows]
            return build_paginated_response(items, total or 0, page, page_size)

        return await run_db(_find_all_paginated)

    @staticmethod
    async def find_one(material_id: int) -> RawMaterialResponse:
        def _find(db: Session) -> RawMaterialResponse:
            result = db.execute(
                select(RawMaterial).where(
                    RawMaterial.id == material_id,
                    RawMaterial.deleted_at.is_(None),
                )
            )
            row = result.scalar_one_or_none()
            if not row:
                raise NotFoundError("RawMaterial", material_id)
            return _to_response(row)
        return await run_db(_find)

    @staticmethod
    async def update(material_id: int, dto: RawMaterialUpdateDto) -> RawMaterialResponse:
        def _update(db: Session) -> RawMaterialResponse:
            result = db.execute(
                select(RawMaterial).where(
                    RawMaterial.id == material_id,
                    RawMaterial.deleted_at.is_(None),
                )
            )
            row = result.scalar_one_or_none()
            if not row:
                raise NotFoundError("RawMaterial", material_id)
            data = dto.model_dump(exclude_unset=True)
            text_fields = ("name", "material_type", "group", "description")
            for k, v in data.items():
                if k in text_fields and isinstance(v, str):
                    v = normalize_unicode(v) or v
                setattr(row, k, v)
            row.updated_at = datetime.utcnow()
            db.flush()
            return _to_response(row)
        return await run_db(_update)

    @staticmethod
    async def adjust_stock(
        material_id: int,
        quantity_delta: Decimal,
        notes: Optional[str] = None,
        user_id: Optional[int] = None,
    ) -> RawMaterialResponse:
        """
        Adjust stock by delta (positive=add, negative=remove), create inventory log.
        Raises if new_qty would be negative.
        """

        def _adjust(db: Session) -> RawMaterialResponse:
            result = db.execute(
                select(RawMaterial).where(
                    RawMaterial.id == material_id,
                    RawMaterial.deleted_at.is_(None),
                )
            )
            row = result.scalar_one_or_none()
            if not row:
                raise NotFoundError("RawMaterial", material_id)
            previous_qty = row.stock_qty
            new_qty = previous_qty + quantity_delta
            if new_qty < 0:
                raise ConflictError(
                    f"Cannot reduce stock by {abs(quantity_delta)}: current stock is {previous_qty}"
                )
            # Determine log type
            if quantity_delta > 0:
                log_type = LogType.ADD
            elif quantity_delta < 0:
                log_type = LogType.REMOVE
            else:
                log_type = LogType.ADJUST
            now = datetime.utcnow()
            row.stock_qty = new_qty
            row.updated_at = now
            log = InventoryLog(
                raw_material_id=material_id,
                user_id=user_id,
                type=log_type.value,
                quantity_delta=quantity_delta,
                previous_qty=previous_qty,
                new_qty=new_qty,
                notes=notes,
                created_at=now,
                updated_at=now,
            )
            db.add(log)
            db.flush()
            return _to_response(row)

        return await run_db(_adjust)

    @staticmethod
    async def remove(material_id: int) -> None:
        def _remove(db: Session) -> None:
            result = db.execute(select(RawMaterial).where(RawMaterial.id == material_id))
            row = result.scalar_one_or_none()
            if not row:
                raise NotFoundError("RawMaterial", material_id)
            row.deleted_at = datetime.utcnow()
            db.flush()
        await run_db(_remove)

    @staticmethod
    async def check_stock(
        below_min_only: bool = True,
        search: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> List[StockCheckResponse]:
        """
        List stock levels. If below_min_only=True, only items where stock_qty < min_stock_req
        (and min_stock_req is set). Optional search filters the list (same word search as find_all).
        Optional limit caps the number of results returned.
        """
        words = search_words(search)

        def _check(db: Session) -> List[StockCheckResponse]:
            query = select(RawMaterial).where(RawMaterial.deleted_at.is_(None))
            if below_min_only:
                query = query.where(
                    RawMaterial.min_stock_req.isnot(None),
                    RawMaterial.stock_qty < RawMaterial.min_stock_req,
                )
            for word in words:
                pattern = f"%{word}%"
                query = query.where(
                    or_(
                        RawMaterial.name.ilike(pattern),
                        RawMaterial.unit_type.ilike(pattern),
                        RawMaterial.material_type.ilike(pattern),
                        RawMaterial.group.ilike(pattern),
                        RawMaterial.description.ilike(pattern),
                    )
                )
            query = query.order_by(RawMaterial.name)
            if limit is not None:
                query = query.limit(limit)
            result = db.execute(query)
            rows = result.scalars().all()
            return [
                StockCheckResponse(
                    id=r.id,
                    name=r.name,
                    stock_qty=r.stock_qty,
                    min_stock_req=r.min_stock_req,
                    below_min=bool(r.min_stock_req is not None and r.stock_qty < r.min_stock_req),
                )
                for r in rows
            ]
        return await run_db(_check)

    @staticmethod
    async def consumption(
        material_id: int,
        page: int = 1,
        page_size: int = 50,
        from_date: Optional[str] = None,
        to_date: Optional[str] = None,
    ) -> ConsumptionResponse:
        from app.modules.production.models import MaterialConsumption
        from app.modules.production.models import Batch
        from app.modules.products.models import Product
        from app.modules.stages.models import Stage

        def _get(db: Session) -> ConsumptionResponse:
            q = (
                select(MaterialConsumption, Batch.batch_no, Product.part_no, Product.name, Stage.name)
                .join(Batch, MaterialConsumption.batch_id == Batch.id)
                .join(Product, Batch.product_id == Product.id)
                .outerjoin(Stage, MaterialConsumption.stage_id == Stage.id)
                .where(
                    MaterialConsumption.raw_material_id == material_id,
                    MaterialConsumption.deleted_at.is_(None),
                    Batch.deleted_at.is_(None),
                )
            )
            if from_date:
                q = q.where(MaterialConsumption.created_at >= from_date)
            if to_date:
                q = q.where(MaterialConsumption.created_at <= to_date + " 23:59:59")
            q = q.order_by(MaterialConsumption.created_at.desc(), MaterialConsumption.id.desc())

            all_rows = db.execute(q).all()
            total = len(all_rows)
            offset = (page - 1) * page_size
            page_rows = all_rows[offset: offset + page_size]

            today = date.today()
            month_start = today.replace(day=1).isoformat()
            total_all = sum(r.qty_consumed for (r, *_) in all_rows if r.qty_consumed)
            total_month = sum(
                r.qty_consumed for (r, *_) in all_rows
                if r.qty_consumed and r.created_at and r.created_at.date() >= today.replace(day=1)
            )

            items = [
                ConsumptionEventLine(
                    id=r.id, batch_id=r.batch_id, batch_no=batch_no,
                    product_part_no=part_no, product_name=prod_name,
                    stage_name=stage_name, qty_consumed=r.qty_consumed,
                    previous_qty=r.previous_qty, new_qty=r.new_qty,
                    created_at=r.created_at,
                )
                for (r, batch_no, part_no, prod_name, stage_name) in page_rows
            ]
            total_pages = max(1, ceil(total / page_size))
            return ConsumptionResponse(
                items=items, total=total, page=page, page_size=page_size,
                total_pages=total_pages, has_more=page < total_pages,
                total_consumed_all_time=total_all,
                total_consumed_this_month=total_month,
            )

        return await run_db(_get)
