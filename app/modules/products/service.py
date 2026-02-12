"""
Products service. find_all with powerful search; get_bom uses BOM module.
"""

from typing import Dict, List, Optional
from sqlalchemy import select, or_
from sqlalchemy.orm import Session
from datetime import datetime
from decimal import Decimal

from app.core.db.engine import run_db
from app.core.exceptions import ConflictError, NotFoundError
from app.core.pagination import paginate_query, build_paginated_response
from app.core.utils import search_words
from app.modules.products.models import Product
from app.modules.products.schemas import (
    ProductCreateDto,
    ProductUpdateDto,
    ProductResponse,
    ProductDetailResponse,
    BOMLineResponse,
    BulkItemResult,
    BulkCreateResponse,
)
from app.modules.bom.service import BOMService as BOMServiceRef


ALLOWED_FIELD_OPTIONS_FIELDS = ("category", "group", "unit_of_measure", "model_name")


def _to_response(row: Product) -> ProductResponse:
    return ProductResponse(
        id=row.id,
        name=row.name,
        category=row.category,
        group=row.group,
        mrp=row.mrp,
        qty=row.qty,
        gst=row.gst,
        hsn=row.hsn,
        part_no=row.part_no,
        model_name=row.model_name,
        is_active=row.is_active,
        product_image=row.product_image,
        distributor_price=row.distributor_price,
        dealer_price=row.dealer_price,
        retail_price=row.retail_price,
        unit_of_measure=row.unit_of_measure,
        created_at=row.created_at,
        updated_at=row.updated_at,
        deleted_at=row.deleted_at,
    )


class ProductService:
    @staticmethod
    async def create(dto: ProductCreateDto) -> ProductResponse:
        def _create(db: Session) -> ProductResponse:
            existing = db.execute(
                select(Product).where(
                    Product.part_no == dto.part_no,
                    Product.deleted_at.is_(None),
                )
            )
            if existing.scalars().first():
                raise ConflictError("Product already exists with this part_no")
            row = Product(
                name=dto.name,
                category=dto.category,
                group=dto.group,
                mrp=dto.mrp,
                qty=dto.qty,
                gst=dto.gst,
                hsn=dto.hsn,
                part_no=dto.part_no,
                model_name=dto.model_name,
                is_active=dto.is_active,
                product_image=dto.product_image,
                distributor_price=dto.distributor_price,
                dealer_price=dto.dealer_price,
                retail_price=dto.retail_price,
                unit_of_measure=dto.unit_of_measure,
            )
            db.add(row)
            db.flush()
            db.refresh(row)
            return _to_response(row)

        return await run_db(_create)

    @staticmethod
    async def bulk_create(items: List[ProductCreateDto]) -> BulkCreateResponse:
        """
        Insert a batch of products. Duplicate part_no is skipped.
        Returns counts and one detail per item (for logging).
        """

        def _bulk(db: Session) -> BulkCreateResponse:
            added = 0
            skipped = 0
            errors = 0
            details: List[BulkItemResult] = []
            for i, dto in enumerate(items):
                one_indexed = i + 1
                try:
                    existing = db.execute(
                        select(Product).where(
                            Product.part_no == dto.part_no,
                            Product.deleted_at.is_(None),
                        )
                    )
                    if existing.scalars().first():
                        skipped += 1
                        details.append(
                            BulkItemResult(
                                index=one_indexed,
                                status="skip",
                                part_no=dto.part_no,
                                message="duplicate part_no",
                            )
                        )
                        continue
                    row = Product(
                        name=dto.name,
                        category=dto.category,
                        group=dto.group,
                        mrp=dto.mrp,
                        qty=dto.qty,
                        gst=dto.gst,
                        hsn=dto.hsn,
                        part_no=dto.part_no,
                        model_name=dto.model_name,
                        is_active=dto.is_active,
                        product_image=dto.product_image,
                        distributor_price=dto.distributor_price,
                        dealer_price=dto.dealer_price,
                        retail_price=dto.retail_price,
                        unit_of_measure=dto.unit_of_measure,
                    )
                    db.add(row)
                    db.flush()
                    added += 1
                    details.append(
                        BulkItemResult(
                            index=one_indexed,
                            status="ok",
                            part_no=dto.part_no,
                            message=dto.name,
                        )
                    )
                except Exception as e:
                    errors += 1
                    details.append(
                        BulkItemResult(
                            index=one_indexed,
                            status="error",
                            part_no=dto.part_no,
                            message=str(e),
                        )
                    )
            db.commit()
            return BulkCreateResponse(
                added=added, skipped=skipped, errors=errors, details=details
            )

        return await run_db(_bulk)

    @staticmethod
    async def find_all(search: Optional[str] = None) -> List[ProductResponse]:
        """
        List non-deleted products. Optional search: split into words;
        each word must match at least one of name, category, group, part_no, model_name, unit_of_measure.
        """
        words = search_words(search)

        def _find_all(db: Session) -> List[ProductResponse]:
            query = select(Product).where(Product.deleted_at.is_(None))
            for word in words:
                pattern = f"%{word}%"
                query = query.where(
                    or_(
                        Product.name.ilike(pattern),
                        Product.category.ilike(pattern),
                        Product.group.ilike(pattern),
                        Product.part_no.ilike(pattern),
                        Product.model_name.ilike(pattern),
                        Product.unit_of_measure.ilike(pattern),
                    )
                )
            query = query.order_by(Product.created_at.desc())
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
        Find all products with pagination and optional search filter.

        CRITICAL: Search filtering happens BEFORE pagination.
        """
        words = search_words(search)

        def _find_all_paginated(db: Session) -> dict:
            query = select(Product).where(Product.deleted_at.is_(None))
            for word in words:
                pattern = f"%{word}%"
                query = query.where(
                    or_(
                        Product.name.ilike(pattern),
                        Product.category.ilike(pattern),
                        Product.group.ilike(pattern),
                        Product.part_no.ilike(pattern),
                        Product.model_name.ilike(pattern),
                        Product.unit_of_measure.ilike(pattern),
                    )
                )
            query = query.order_by(Product.created_at.desc())

            products, total = paginate_query(db, query, page, page_size)
            items = [_to_response(r) for r in products]
            return build_paginated_response(items, total, page, page_size)

        return await run_db(_find_all_paginated)

    @staticmethod
    async def get_field_options(
        fields: Optional[List[str]] = None,
    ) -> Dict[str, List[str]]:

        requested = (
            [f for f in fields if f in ALLOWED_FIELD_OPTIONS_FIELDS]
            if fields
            else list(ALLOWED_FIELD_OPTIONS_FIELDS)
        )
        print("requested", requested)

        if not requested:
            return {}

        def _get_options(db: Session) -> Dict[str, List[str]]:
            cols = [getattr(Product, f) for f in requested]

            stmt = select(*cols).where(Product.deleted_at.is_(None))

            rows = db.execute(stmt).all()
            print("rows", len(rows))

            out: Dict[str, set] = {f: set() for f in requested}

            for row in rows:
                for idx, field in enumerate(requested):
                    value = row[idx]
                    if value is not None:
                        out[field].add(str(value))

            return {field: sorted(values) for field, values in out.items()}

        return await run_db(_get_options)

    @staticmethod
    async def find_one(product_id: int) -> ProductResponse:
        def _find(db: Session) -> ProductResponse:
            result = db.execute(
                select(Product).where(
                    Product.id == product_id,
                    Product.deleted_at.is_(None),
                )
            )
            row = result.scalar_one_or_none()
            if not row:
                raise NotFoundError("Product", product_id)
            return _to_response(row)

        return await run_db(_find)

    @staticmethod
    async def find_one_with_bom(
        product_id: int, variant: Optional[str] = None
    ) -> ProductDetailResponse:
        """Product by id with BOM grouped by variant."""
        base = await ProductService.find_one(product_id)
        bom_lines = await BOMServiceRef.find_by_product(product_id, variant=None)
        bom_by_variant: dict = {}
        for l in bom_lines:
            key = l.variant if l.variant else "Default"
            line = BOMLineResponse(
                raw_material_id=l.raw_material_id,
                raw_material_name=l.raw_material_name,
                variant=l.variant,
                batch_qty=l.batch_qty,
                raw_qty=l.raw_qty,
            )
            if key not in bom_by_variant:
                bom_by_variant[key] = []
            bom_by_variant[key].append(line)
        return ProductDetailResponse(**base.model_dump(), bom_by_variant=bom_by_variant)

    @staticmethod
    async def get_bom(
        product_id: int, variant: Optional[str] = None
    ) -> List[BOMLineResponse]:
        """Get BOM for product (and optional variant) from BOM module."""
        await ProductService.find_one(product_id)
        bom_lines = await BOMServiceRef.find_by_product(product_id, variant=variant)
        return [
            BOMLineResponse(
                raw_material_id=l.raw_material_id,
                raw_material_name=l.raw_material_name,
                variant=l.variant,
                batch_qty=l.batch_qty,
                raw_qty=l.raw_qty,
            )
            for l in bom_lines
        ]

    @staticmethod
    async def update(product_id: int, dto: ProductUpdateDto) -> ProductResponse:
        def _update(db: Session) -> ProductResponse:
            result = db.execute(
                select(Product).where(
                    Product.id == product_id,
                    Product.deleted_at.is_(None),
                )
            )
            row = result.scalar_one_or_none()
            if not row:
                raise NotFoundError("Product", product_id)
            data = dto.model_dump(exclude_unset=True)
            for k, v in data.items():
                setattr(row, k, v)
            db.flush()
            db.refresh(row)
            return _to_response(row)

        return await run_db(_update)

    @staticmethod
    async def remove(product_id: int) -> None:
        def _remove(db: Session) -> None:
            result = db.execute(select(Product).where(Product.id == product_id))
            row = result.scalar_one_or_none()
            if not row:
                raise NotFoundError("Product", product_id)
            row.deleted_at = datetime.utcnow()
            db.flush()

        await run_db(_remove)
