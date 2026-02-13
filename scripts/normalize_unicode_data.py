#!/usr/bin/env python3
"""
One-time script to normalize existing Unicode text (Gujarati, etc.) to NFC form.

Ensures raw materials, products, BOM, and job rates have consistent NFC storage
so search works reliably with mixed English/Gujarati data.

Run from project root:
    cd server && python -m scripts.normalize_unicode_data

Options:
    --dry-run   Print what would be updated without writing to DB
"""

import argparse
import sys
from pathlib import Path

# Add server to path so app imports work
SERVER_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SERVER_DIR))

from dotenv import load_dotenv
load_dotenv(SERVER_DIR / ".env")

from sqlalchemy import select

from app.core.db.engine import SessionLocal
from app.core.utils import normalize_unicode
from app.modules.raw_materials.models import RawMaterial
from app.modules.products.models import Product
from app.modules.bom.models import BOMLine
from app.modules.job_rates.models import JobRate


def _normalize_field(value: str | None) -> str | None:
    if value is None or not isinstance(value, str):
        return value
    normalized = normalize_unicode(value)
    return normalized if normalized != value else None  # None = no change needed


def normalize_raw_materials(db, dry_run: bool) -> int:
    """Normalize raw_materials text fields. Returns count updated."""
    rows = db.execute(select(RawMaterial)).scalars().all()
    count = 0
    for rm in rows:
        updates = {}
        for field in ("name", "material_type", "group", "description"):
            new_val = _normalize_field(getattr(rm, field))
            if new_val is not None:
                updates[field] = new_val
        if updates:
            if not dry_run:
                for k, v in updates.items():
                    setattr(rm, k, v)
            count += 1
    return count


def normalize_products(db, dry_run: bool) -> int:
    """Normalize products text fields. Returns count updated."""
    rows = db.execute(select(Product)).scalars().all()
    count = 0
    for p in rows:
        updates = {}
        for field in ("name", "category", "group", "model_name", "unit_of_measure"):
            new_val = _normalize_field(getattr(p, field))
            if new_val is not None:
                updates[field] = new_val
        if updates:
            if not dry_run:
                for k, v in updates.items():
                    setattr(p, k, v)
            count += 1
    return count


def normalize_bom(db, dry_run: bool) -> int:
    """Normalize BOM variant field. Returns count updated."""
    rows = db.execute(select(BOMLine)).scalars().all()
    count = 0
    for b in rows:
        new_val = _normalize_field(b.variant)
        if new_val is not None:
            if not dry_run:
                b.variant = new_val
            count += 1
    return count


def normalize_job_rates(db, dry_run: bool) -> int:
    """Normalize job_rates operation_code and operation_name. Returns count updated."""
    rows = db.execute(select(JobRate)).scalars().all()
    count = 0
    for jr in rows:
        updates = {}
        for field in ("operation_code", "operation_name"):
            new_val = _normalize_field(getattr(jr, field))
            if new_val is not None:
                updates[field] = new_val
        if updates:
            if not dry_run:
                for k, v in updates.items():
                    setattr(jr, k, v)
            count += 1
    return count


def _safe_normalize(name: str, fn, db, dry_run: bool) -> int:
    """Run normalizer, return count. Returns 0 and prints skip message if table doesn't exist."""
    try:
        return fn(db, dry_run)
    except Exception as e:
        if "no such table" in str(e).lower():
            print(f"  Skipping {name} (table not found)")
            return 0
        raise


def main():
    parser = argparse.ArgumentParser(
        description="Normalize existing Unicode text (Gujarati, etc.) to NFC for consistent search"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print what would be updated without writing to DB",
    )
    args = parser.parse_args()

    print("Normalizing Unicode text to NFC...")
    if args.dry_run:
        print("(dry run - no changes will be made)")

    with SessionLocal() as db:
        rm_count = _safe_normalize("raw_materials", normalize_raw_materials, db, args.dry_run)
        prod_count = _safe_normalize("products", normalize_products, db, args.dry_run)
        bom_count = _safe_normalize("bom_lines", normalize_bom, db, args.dry_run)
        jr_count = _safe_normalize("job_rates", normalize_job_rates, db, args.dry_run)

        if not args.dry_run:
            db.commit()

    print(f"Raw materials: {rm_count} updated")
    print(f"Products: {prod_count} updated")
    print(f"BOM lines: {bom_count} updated")
    print(f"Job rates: {jr_count} updated")
    total = rm_count + prod_count + bom_count + jr_count
    print(f"Total: {total} records normalized")


if __name__ == "__main__":
    main()
