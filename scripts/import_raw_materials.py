#!/usr/bin/env python3
"""
Import the raw-material master from new-data/raw-materials.csv into `raw_materials`.

CSV columns (by position):
  0 Name  1 Unit Type  2 Material Type  3 Group  4 Min. Stock Req.  5 Min. Order Qty.
  6 Stock Qty.  7 GST  8 HSN  9 Purchase Price  10 Description  11 Treat as consume?(Y/N)
  12 Status(Y/N)   13-15 = stray "Unnamed" legend columns -> IGNORED

Notes:
  - name is unique: blank or already-seen names are skipped + reported.
  - Real CSV parser handles inch-marks in names (1" BUCKLE, CHAIN 12.5").
  - Y/N -> bool: treat_as_consume (blank=False), is_active from Status (blank=False; the
    blank-status rows are the discontinued / zero-stock items).
  - blank numeric -> NULL; stock_qty blank -> 0. unit_type blank -> 'PC' (NOT NULL) + reported.

Run from server/ :
    python -m scripts.import_raw_materials                 # live import
    python -m scripts.import_raw_materials --dry-run
    python -m scripts.import_raw_materials --skip-existing  # idempotent re-run
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
from app.modules.raw_materials.models import RawMaterial


def s(v):
    v = (v or "").strip()
    if not v:
        return None
    return normalize_unicode(v) or v


def num(v):
    v = (v or "").strip()
    if not v:
        return None
    try:
        return Decimal(v)
    except (InvalidOperation, ValueError):
        return None


def yn(v, default=False):
    v = (v or "").strip().upper()
    if v == "Y":
        return True
    if v == "N":
        return False
    return default


def load_csv(csv_path: Path):
    rows, no_unit = [], 0
    with open(csv_path, encoding="utf-8") as f:
        reader = csv.reader(f)
        next(reader, None)  # header
        for r in reader:
            if len(r) < 2:
                continue
            name = (r[0] or "").strip()
            if not name:
                continue
            unit = (r[1] or "").strip() if len(r) > 1 else ""
            if not unit:
                no_unit += 1
                unit = "PC"
            rows.append({
                "name": s(r[0]),
                "unit_type": unit,
                "material_type": s(r[2]) if len(r) > 2 else None,
                "group": s(r[3]) if len(r) > 3 else None,
                "min_stock_req": num(r[4]) if len(r) > 4 else None,
                "min_order_qty": num(r[5]) if len(r) > 5 else None,
                "stock_qty": num(r[6]) if len(r) > 6 and (r[6] or "").strip() else Decimal("0"),
                "gst": s(r[7]) if len(r) > 7 else None,
                "hsn": s(r[8]) if len(r) > 8 else None,
                "purchase_price": num(r[9]) if len(r) > 9 else None,
                "description": s(r[10]) if len(r) > 10 else None,
                "treat_as_consume": yn(r[11] if len(r) > 11 else "", default=False),
                "is_active": yn(r[12] if len(r) > 12 else "", default=False),
            })
    return rows, no_unit


def run_import(csv_path: Path, skip_existing: bool, dry_run: bool):
    rows, no_unit = load_csv(csv_path)
    if not rows:
        print("No rows found in CSV.")
        return

    added = skipped = dup_in_csv = 0
    seen = set()

    with SessionLocal() as db:
        existing_names = set()
        if skip_existing:
            existing_names = {
                n for (n,) in db.execute(
                    select(RawMaterial.name).where(RawMaterial.deleted_at.is_(None))
                ).all()
            }

        for row in rows:
            nm = row["name"]
            if nm in seen:
                dup_in_csv += 1
                continue
            seen.add(nm)

            if skip_existing and nm in existing_names:
                skipped += 1
                continue

            if dry_run:
                added += 1
                continue

            db.add(RawMaterial(**row))
            added += 1

        if not dry_run:
            db.commit()

    print("\n=========== IMPORT RAW MATERIALS ===========")
    print(f"rows in CSV (valid name)  : {len(rows)}")
    print(f"{'WOULD ADD' if dry_run else 'added'}                 : {added}")
    print(f"skipped (already in DB)   : {skipped}")
    print(f"duplicate name in CSV     : {dup_in_csv}")
    print(f"blank unit_type -> 'PC'   : {no_unit}")
    print()


def main():
    parser = argparse.ArgumentParser(description="Import raw materials from raw-materials.csv")
    default_csv = SERVER_DIR.parent / "new-data" / "raw-materials.csv"
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
