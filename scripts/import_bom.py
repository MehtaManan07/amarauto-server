#!/usr/bin/env python3
"""
Import the BOM (recipe) from new-data/bom.csv into `bom_lines`.

CSV columns (by position):
  0 Product (Part No.)  1 BOM(style/variant)  2 colour  3 QTY(batch_size)
  4 raw mat  5 qty(qty_per_batch)  6 stage

Rules baked in:
  - SUM, DON'T DEDUP: every CSV row becomes its own bom_line. Two rows for the same
    product+style+colour+stage+material are REAL (e.g. main panel 9.22m + trim 1.66m);
    consumption later SUMs over the lines. We never collapse them.
  - batch_size = QTY (the recipe's standard batch), qty_per_batch = qty (total for one batch).
    per-unit = qty_per_batch / batch_size.
  - Resolves product (part_no), raw_material (NFC name), stage (name) against the DB.
    Rows whose product or raw material isn't in the DB are SKIPPED + reported (the tail:
    ~38 cushport rows + 8 with 2 missing raw mats). Re-run after the recipe editor adds them.
  - IDEMPOTENT by product: products that already have any bom_line are skipped, so re-runs
    never double a recipe (use --force to override).

FAST upload: rows are inserted as chunked multi-row INSERTs (one statement per CHUNK rows),
so ~2085 rows = ~11 round-trips, not 2085. Parameterized — no quote-escaping hazards.
Use --emit-sql FILE to instead write a .sql file for `turso db shell amarauto < FILE`.

Run from server/ :
    python -m scripts.import_bom                  # live import (chunked)
    python -m scripts.import_bom --dry-run        # report only
    python -m scripts.import_bom --emit-sql ../bom_seed.sql   # write SQL file, no DB writes
    python -m scripts.import_bom --force          # re-import even if products already have BOM
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

from sqlalchemy import select, insert

from app.core.db.engine import SessionLocal
from app.core.utils import normalize_unicode
from app.modules.products.models import Product
from app.modules.raw_materials.models import RawMaterial
from app.modules.stages.models import Stage
from app.modules.bom.models import BOMLine

CHUNK = 200


def s(v):
    v = (v or "").strip()
    return v or None


def nfc(v):
    v = (v or "").strip()
    if not v:
        return None
    return normalize_unicode(v) or v


def num(v, default=None):
    v = (v or "").strip()
    if not v:
        return default
    try:
        return Decimal(v)
    except (InvalidOperation, ValueError):
        return default


def load_csv(csv_path: Path):
    rows = []
    with open(csv_path, encoding="utf-8") as f:
        reader = csv.reader(f)
        next(reader, None)  # header
        for r in reader:
            if len(r) < 7 or not (r[0] or "").strip():
                continue
            rows.append(r)
    return rows


def build_lines(rows, parts, rms, stages, skip_products):
    """Resolve rows -> list of bom_line dicts. Returns (lines, stats)."""
    lines = []
    skipped_no_product = skipped_no_rm = skipped_no_qty = skipped_existing = 0
    miss_p, miss_r = set(), set()

    for r in rows:
        part_no = r[0].strip()
        rm_name = nfc(r[4])
        product_id = parts.get(part_no)
        rm_id = rms.get(rm_name)

        if product_id is None:
            skipped_no_product += 1
            miss_p.add(part_no)
            continue
        if rm_id is None:
            skipped_no_rm += 1
            miss_r.add(rm_name)
            continue
        if product_id in skip_products:
            skipped_existing += 1
            continue

        qty_per_batch = num(r[5])
        if qty_per_batch is None:
            skipped_no_qty += 1
            continue

        lines.append({
            "product_id": product_id,
            "stage_id": stages.get((r[6] or "").strip().lower()),
            "style": s(r[1]),
            "colour": s(r[2]),
            "raw_material_id": rm_id,
            "batch_size": num(r[3], default=Decimal("1")) or Decimal("1"),
            "qty_per_batch": qty_per_batch,
        })

    stats = {
        "skipped_no_product": skipped_no_product,
        "skipped_no_rm": skipped_no_rm,
        "skipped_no_qty": skipped_no_qty,
        "skipped_existing": skipped_existing,
        "miss_p": sorted(miss_p),
        "miss_r": sorted(miss_r),
    }
    return lines, stats


def emit_sql(lines, out_path: Path):
    """Write chunked multi-row INSERTs to a .sql file (for `turso db shell`)."""
    def lit(v):
        if v is None:
            return "NULL"
        if isinstance(v, Decimal):
            return str(v)
        return "'" + str(v).replace("'", "''") + "'"

    cols = ["product_id", "stage_id", "style", "colour", "raw_material_id",
            "batch_size", "qty_per_batch"]
    with open(out_path, "w", encoding="utf-8") as f:
        f.write("BEGIN;\n")
        for i in range(0, len(lines), CHUNK):
            chunk = lines[i:i + CHUNK]
            f.write(f"INSERT INTO bom_lines ({', '.join(cols)}) VALUES\n")
            vals = [",\n".join(
                "(" + ", ".join(lit(row[c]) for c in cols) + ")" for row in chunk
            )]
            f.write(vals[0] + ";\n")
        f.write("COMMIT;\n")


def run(csv_path: Path, dry_run: bool, force: bool, sql_out: Path | None):
    rows = load_csv(csv_path)
    if not rows:
        print("No rows found in CSV.")
        return

    with SessionLocal() as db:
        parts = {p: i for (p, i) in db.execute(
            select(Product.part_no, Product.id).where(Product.deleted_at.is_(None))
        ).all()}
        rms = {(normalize_unicode(n) or n): i for (n, i) in db.execute(
            select(RawMaterial.name, RawMaterial.id).where(RawMaterial.deleted_at.is_(None))
        ).all()}
        stages = {n.lower(): i for (n, i) in db.execute(
            select(Stage.name, Stage.id).where(Stage.deleted_at.is_(None))
        ).all()}

        skip_products = set()
        if not force:
            skip_products = {
                pid for (pid,) in db.execute(
                    select(BOMLine.product_id).where(BOMLine.deleted_at.is_(None)).distinct()
                ).all()
            }

        lines, st = build_lines(rows, parts, rms, stages, skip_products)

        inserted = 0
        if sql_out is not None:
            emit_sql(lines, sql_out)
        elif not dry_run:
            for i in range(0, len(lines), CHUNK):
                db.execute(insert(BOMLine).values(lines[i:i + CHUNK]))
                inserted += len(lines[i:i + CHUNK])
            db.commit()
        else:
            inserted = len(lines)

    print("\n=========== IMPORT BOM ===========")
    print(f"rows in CSV                  : {len(rows)}")
    if sql_out is not None:
        print(f"SQL written to               : {sql_out}  ({len(lines)} bom_lines)")
        print(f"  -> run: turso db shell amarauto < {sql_out}")
    else:
        print(f"bom_lines {'WOULD ADD' if dry_run else 'inserted '}        : {len(lines) if dry_run else inserted}")
    print(f"skipped: unmatched product   : {st['skipped_no_product']}  ({len(st['miss_p'])} distinct: {st['miss_p'][:6]})")
    print(f"skipped: unmatched raw mat   : {st['skipped_no_rm']}  ({len(st['miss_r'])} distinct: {st['miss_r'][:6]})")
    print(f"skipped: missing qty         : {st['skipped_no_qty']}")
    print(f"skipped: product already has BOM (idempotent): {st['skipped_existing']}")
    print()


def main():
    ap = argparse.ArgumentParser(description="Import BOM from bom.csv")
    ap.add_argument("--csv", type=Path, default=SERVER_DIR.parent / "new-data" / "bom.csv")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--force", action="store_true",
                    help="import even for products that already have bom_lines")
    ap.add_argument("--emit-sql", type=Path, default=None,
                    help="write INSERTs to this .sql file instead of writing to the DB")
    args = ap.parse_args()

    if not args.csv.exists():
        print(f"CSV not found: {args.csv}")
        sys.exit(1)

    print(f"Importing from {args.csv}")
    if args.dry_run:
        print("(dry run — no changes will be made)")
    run(args.csv, args.dry_run, args.force, args.emit_sql)


if __name__ == "__main__":
    main()
