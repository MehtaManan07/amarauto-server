#!/usr/bin/env python3
"""
Import the product master from new-data/products.csv into the `products` table.

CSV columns (by position):
  0 Product Name  1 Category  2 Group  3 MRP  4 Qty.  5 GST  6 HSN  7 Part No.
  8 Model Name  9 Status(Y/N)  10 Product Image  11 Distributor  12 Dealer
  13 Retail  14 unit of measure

part_no is required + unique: rows with a blank part_no, or a part_no already seen, are
skipped and reported. is_manufactured / is_component default False (set later in the recipe
editor — most products are catalog-only).

Run from server/ :
    python -m scripts.import_products                 # live import
    python -m scripts.import_products --dry-run
    python -m scripts.import_products --skip-existing  # idempotent re-run
"""

import argparse
import csv
import sys
from decimal import Decimal, InvalidOperation
from pathlib import Path

SERVER_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SERVER_DIR))

from dotenv import load_dotenv

load_dotenv(SERVER_DIR / ".env")

from sqlalchemy import select

from app.core.db.engine import SessionLocal
from app.core.utils import normalize_unicode
from app.modules.products.models import Product


def s(v):
    """Trim + NFC-normalize a text cell, or None if blank."""
    v = (v or "").strip()
    if not v:
        return None
    return normalize_unicode(v) or v


def num(v):
    """Decimal or None."""
    v = (v or "").strip()
    if not v:
        return None
    try:
        return Decimal(v)
    except (InvalidOperation, ValueError):
        return None


def yn(v, default=True):
    v = (v or "").strip().upper()
    if v == "Y":
        return True
    if v == "N":
        return False
    return default


def load_csv(csv_path: Path) -> list[dict]:
    rows = []
    with open(csv_path, encoding="utf-8") as f:
        reader = csv.reader(f)
        next(reader, None)  # header
        for r in reader:
            if len(r) < 8:
                continue
            part_no = (r[7] or "").strip()
            name = (r[0] or "").strip()
            if not part_no or not name:
                continue
            rows.append({
                "name": s(r[0]),
                "category": s(r[1]) if len(r) > 1 else None,
                "group": s(r[2]) if len(r) > 2 else None,
                "mrp": num(r[3]) if len(r) > 3 else None,
                "qty": num(r[4]) if len(r) > 4 else None,
                "gst": s(r[5]) if len(r) > 5 else None,
                "hsn": s(r[6]) if len(r) > 6 else None,
                "part_no": part_no,
                "model_name": s(r[8]) if len(r) > 8 else None,
                "is_active": yn(r[9] if len(r) > 9 else "", default=True),
                "product_image": s(r[10]) if len(r) > 10 else None,
                "distributor_price": num(r[11]) if len(r) > 11 else None,
                "dealer_price": num(r[12]) if len(r) > 12 else None,
                "retail_price": num(r[13]) if len(r) > 13 else None,
                "unit_of_measure": s(r[14]) if len(r) > 14 else None,
            })
    return rows


def run_import(csv_path: Path, skip_existing: bool, dry_run: bool):
    rows = load_csv(csv_path)
    if not rows:
        print("No rows found in CSV.")
        return

    added = skipped = dup_in_csv = 0
    seen_parts = set()

    with SessionLocal() as db:
        existing_parts = set()
        if skip_existing:
            existing_parts = {
                p for (p,) in db.execute(
                    select(Product.part_no).where(Product.deleted_at.is_(None))
                ).all()
            }

        for row in rows:
            pn = row["part_no"]
            if pn in seen_parts:
                dup_in_csv += 1
                continue
            seen_parts.add(pn)

            if skip_existing and pn in existing_parts:
                skipped += 1
                continue

            if dry_run:
                added += 1
                continue

            db.add(Product(**row))
            added += 1

        if not dry_run:
            db.commit()

    print("\n=========== IMPORT PRODUCTS ===========")
    print(f"rows in CSV (valid part_no): {len(rows)}")
    print(f"{'WOULD ADD' if dry_run else 'added'}                  : {added}")
    print(f"skipped (already in DB)    : {skipped}")
    print(f"duplicate part_no in CSV   : {dup_in_csv}")
    print()


def main():
    parser = argparse.ArgumentParser(description="Import products from products.csv")
    default_csv = SERVER_DIR.parent / "new-data" / "products.csv"
    parser.add_argument("--csv", type=Path, default=default_csv)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--skip-existing", action="store_true")
    args = parser.parse_args()

    if not args.csv.exists():
        print(f"CSV not found: {args.csv}")
        sys.exit(1)

    print(f"Importing from {args.csv}")
    if args.dry_run:
        print("(dry run — no changes will be made)")
    run_import(args.csv, args.skip_existing, args.dry_run)


if __name__ == "__main__":
    main()
