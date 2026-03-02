"""
Raw materials service. find_all with powerful search; check_stock for low/below-min.
"""

from typing import Dict, List, Optional
from sqlalchemy import select, or_, union_all, literal
from sqlalchemy.orm import Session
from datetime import datetime
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
            )
            db.add(row)
            db.flush()
            db.refresh(row)
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

            for dto in items:
                try:
                    if dto.name in existing_names:
                        results.append(BulkUploadItemResult(
                            name=dto.name,
                            success=False,
                            error="Material with this name already exists",
                            data=None,
                        ))
                        failure_count += 1
                        continue

                    # Create new material
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
                    )
                    db.add(row)
                    db.flush()
                    db.refresh(row)

                    results.append(BulkUploadItemResult(
                        name=dto.name,
                        success=True,
                        error=None,
                        data=_to_response(row),
                    ))
                    success_count += 1

                except Exception as e:
                    results.append(BulkUploadItemResult(
                        name=dto.name,
                        success=False,
                        error=str(e),
                        data=None,
                    ))
                    failure_count += 1

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
            db.flush()
            db.refresh(row)
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
            row.stock_qty = new_qty
            log = InventoryLog(
                raw_material_id=material_id,
                user_id=user_id,
                type=log_type.value,
                quantity_delta=quantity_delta,
                previous_qty=previous_qty,
                new_qty=new_qty,
                notes=notes,
            )
            db.add(log)
            db.flush()
            db.refresh(row)
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
    ) -> List[StockCheckResponse]:
        """
        List stock levels. If below_min_only=True, only items where stock_qty < min_stock_req
        (and min_stock_req is set). Optional search filters the list (same word search as find_all).
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
