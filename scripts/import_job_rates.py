#!/usr/bin/env python3
"""
Import job rate data from data/job-rate-list.csv into the database.

Run from project root:
    cd server && python -m scripts.import_job_rates

Or with explicit path to CSV:
    cd server && python -m scripts.import_job_rates --csv ../data/job-rate-list.csv

Options:
    --csv PATH    Path to CSV (default: ../data/job-rate-list.csv relative to server/)
    --skip-existing  Skip rows where (product_id, operation_code) already exists
    --dry-run     Print what would be imported without writing to DB
"""

import argparse
import csv
import sys
from pathlib import Path

# Add server to path so app imports work
SERVER_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SERVER_DIR))

from dotenv import load_dotenv
load_dotenv(SERVER_DIR / ".env")

from sqlalchemy import select
from decimal import Decimal

from app.core.db.engine import SessionLocal
from app.core.utils import normalize_unicode
from app.modules.products.models import Product
from app.modules.job_rates.models import JobRate


def load_csv(csv_path: Path) -> list[dict]:
    """Load CSV and return list of dicts with keys: product_part_no, operation_code, operation_name, rate."""
    rows = []
    with open(csv_path, encoding="utf-8") as f:
        reader = csv.reader(f)
        next(reader, None)  # skip first row (Unnamed: 0, Unnamed: 1, ...)
        next(reader, None)  # skip second row (PRODUCT, Operation CODE, ...) - header
        for row in reader:
            if len(row) < 4:
                continue
            part_no = str(row[0]).strip()
            op_code = str(row[1]).strip()
            op_name = str(row[2]).strip()
            rate_str = str(row[3]).strip()
            if not part_no or not op_code or not op_name or not rate_str:
                continue
            try:
                rate = Decimal(rate_str)
            except (ValueError, TypeError):
                continue
            rows.append({
                "product_part_no": part_no,
                "operation_code": normalize_unicode(op_code) or op_code,
                "operation_name": normalize_unicode(op_name) or op_name,
                "rate": rate,
            })
    return rows


def run_import(csv_path: Path, skip_existing: bool, dry_run: bool) -> tuple[int, int, int]:
    """Import job rates. Returns (added, skipped, errors)."""
    rows = load_csv(csv_path)
    if not rows:
        print("No rows found in CSV.")
        return 0, 0, 0

    part_no_to_id: dict[str, int] = {}
    sequence_by_product: dict[int, int] = {}
    added = 0
    skipped = 0
    errors = 0

    with SessionLocal() as db:
        # Build part_no -> product_id map
        products = db.execute(
            select(Product).where(Product.deleted_at.is_(None))
        ).scalars().all()
        for p in products:
            part_no_to_id[p.part_no] = p.id

        for row in rows:
            part_no = row["product_part_no"]
            product_id = part_no_to_id.get(part_no)
            if not product_id:
                print(f"  SKIP: Product part_no '{part_no}' not found")
                errors += 1
                continue

            if skip_existing:
                existing = db.execute(
                    select(JobRate).where(
                        JobRate.product_id == product_id,
                        JobRate.operation_code == row["operation_code"],
                        JobRate.deleted_at.is_(None),
                    )
                ).scalar_one_or_none()
                if existing:
                    skipped += 1
                    continue

            if dry_run:
                # print(f"  WOULD ADD: {part_no} | {row['operation_code']} | {row['operation_name']} | {row['rate']}")
                added += 1
                continue

            seq = sequence_by_product.get(product_id, 0) + 1
            sequence_by_product[product_id] = seq

            jr = JobRate(
                product_id=product_id,
                operation_code=row["operation_code"],
                operation_name=row["operation_name"],
                rate=row["rate"],
                sequence=seq,
            )
            db.add(jr)
            added += 1

        if not dry_run:
            db.commit()

    return added, skipped, errors


def main():
    parser = argparse.ArgumentParser(description="Import job rates from CSV")
    default_csv = Path(__file__).resolve().parent.parent.parent / "data" / "job-rate-list.csv"
    parser.add_argument(
        "--csv",
        type=Path,
        default=default_csv,
        help=f"Path to CSV (default: {default_csv})",
    )
    parser.add_argument(
        "--skip-existing",
        action="store_true",
        help="Skip rows where (product_id, operation_code) already exists",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print what would be imported without writing to DB",
    )
    args = parser.parse_args()

    if not args.csv.exists():
        print(f"CSV not found: {args.csv}")
        sys.exit(1)

    print(f"Importing from {args.csv}")
    if args.dry_run:
        print("(dry run - no changes will be made)")
    if args.skip_existing:
        print("(skipping existing product+operation_code pairs)")

    added, skipped, errors = run_import(args.csv, args.skip_existing, args.dry_run)
    print(f"Done: added={added}, skipped={skipped}, errors={errors}")


if __name__ == "__main__":
    main()
