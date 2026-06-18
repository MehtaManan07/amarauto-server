#!/usr/bin/env python3
"""
Import operations (was job_rates) from new-data/job-list.csv into the `operations` table.

Uses the v3 COMBINED resolver (exact PRODUCT-column match UNION operation-code prefix) to
map each operation to a product, and parses the code into component / sequence / side. Stage
is guessed from the Gujarati operation name. Of 288 operations, ~164 resolve today; the rest
are skipped and printed (they need client data-fill: 14 missing products + 8 Cushport parts).

Prereqs: products + stages must already be in the DB (run the baseline migration, then import
products) — this resolves against the DB, not the CSV.

Run from the server/ directory:
    python -m scripts.import_operations                 # live import
    python -m scripts.import_operations --dry-run       # report only, no writes
    python -m scripts.import_operations --skip-existing # idempotent re-run

Options:
    --csv PATH         Path to job-list.csv (default: ../new-data/job-list.csv)
    --dry-run          Print what would happen, write nothing
    --skip-existing    Skip rows where (product_id, code) already exists
"""

import argparse
import csv
import re
import sys
from collections import defaultdict
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
from app.modules.stages.models import Stage
from app.modules.operations.models import Operation, PendingOperation


# --- operation-code parser (mirrors verify_operation_codes.py v3) -------------------
NORM_RE = re.compile(r"0*(\d+)")           # strip leading zeros per numeric run
SIDE_RE = re.compile(r"(?<=\d)([LRF])$")   # trailing L/R/F right after a digit
SEQ_RE = re.compile(r"(\d+)$")             # trailing digits = sequence

STAGE_KEYWORDS = {
    "cutting": ["કટિંગ", "કાપ", "કટ", "કાટ", "cut"],
    "stitching": ["સિલાઈ", "સીલાઈ", "સિવ", "stitch"],
    "finishing": ["જોઇન્ટ", "પેક", "ભરાઈ", "ભરવ", "ફિનિશ", "બોક્સ", "ઇસ્ત્રી",
                  "ફિટ", "ફીટીંગ", "join", "pack", "box", "final"],
}


def normalize_part(pn: str) -> str:
    """A001 -> A1, AS01 -> AS1, A003V -> A3V."""
    return NORM_RE.sub(lambda m: m.group(1), pn)


def guess_stage(name: str) -> str:
    for stage in ("cutting", "stitching", "finishing"):
        if any(kw in (name or "") for kw in STAGE_KEYWORDS[stage]):
            return stage
    return ""


def parse_code(code: str, prefix_map: dict) -> dict:
    """Return {side, seq, product(part_no or None), component}."""
    raw = (code or "").strip()

    side = ""
    m = SIDE_RE.search(raw)
    core = raw
    if m:
        side, core = m.group(1), raw[: m.start()]

    seq = None
    m = SEQ_RE.search(core)
    stem = core
    if m:
        seq, stem = int(m.group(1)), core[: m.start()]
    stem = stem.rstrip("-")

    nodash = stem.replace("-", "")
    product, component = None, ""
    for L in range(len(nodash), 0, -1):
        if nodash[:L] in prefix_map:
            product = prefix_map[nodash[:L]]
            component = nodash[L:]
            break
    if product is None:
        component = nodash

    return {"side": side, "seq": seq, "product": product, "component": component}


def parse_rate(rate_str: str):
    """Return Decimal or None (a few ops have missing rates -> client fills)."""
    s = (rate_str or "").strip()
    if not s:
        return None
    try:
        return Decimal(s)
    except (InvalidOperation, ValueError):
        return None


def load_csv(csv_path: Path) -> list[dict]:
    rows = []
    with open(csv_path, encoding="utf-8") as f:
        reader = csv.reader(f)
        next(reader, None)  # single header row: PRODUCT, Operation CODE, operation name, RATE
        for row in reader:
            if len(row) < 2 or not row[1].strip():
                continue
            rows.append({
                "product_col": row[0].strip(),
                "code": row[1].strip(),
                "name": (row[2].strip() if len(row) > 2 else ""),
                "rate": (row[3].strip() if len(row) > 3 else ""),
            })
    return rows


def run_import(csv_path: Path, skip_existing: bool, dry_run: bool):
    rows = load_csv(csv_path)
    if not rows:
        print("No rows found in CSV.")
        return

    added = skipped = unresolved = stage_unknown = 0
    pending_added = pending_skipped = 0
    unresolved_keys: dict = defaultdict(int)

    with SessionLocal() as db:
        # Resolve against the DB master, not the CSV.
        products = db.execute(
            select(Product).where(Product.deleted_at.is_(None))
        ).scalars().all()
        part_to_id = {p.part_no: p.id for p in products}
        master = set(part_to_id.keys())
        prefix_map: dict[str, str] = {}
        for pn in sorted(master):                 # sorted -> deterministic prefix wins
            prefix_map.setdefault(normalize_part(pn), pn)

        stages = db.execute(
            select(Stage).where(Stage.deleted_at.is_(None))
        ).scalars().all()
        stage_to_id = {s.name.lower(): s.id for s in stages}  # case-insensitive (DB names are UPPER)
        if not stage_to_id:
            print("WARNING: no stages in DB — run the baseline migration first.")

        existing_pairs = set()
        if skip_existing:
            for op in db.execute(
                select(Operation.product_id, Operation.code).where(
                    Operation.deleted_at.is_(None)
                )
            ).all():
                existing_pairs.add((op[0], op[1]))

        # Always dedup the staging table on raw_code so re-runs don't duplicate pendings.
        existing_pending = {
            code for (code,) in db.execute(
                select(PendingOperation.raw_code).where(
                    PendingOperation.deleted_at.is_(None)
                )
            ).all()
        }

        for r in rows:
            p = parse_code(r["code"], prefix_map)
            # combined resolver: exact column match UNION code-prefix match
            col_match = r["product_col"] if r["product_col"] in master else None
            final_part = col_match or p["product"]
            stage_id = stage_to_id.get(guess_stage(r["name"]))  # None if unguessed

            if not final_part:
                # Unmapped -> stage into pending_operations (the Operations Inbox).
                unresolved += 1
                unresolved_keys[(r["product_col"], p["component"])] += 1
                if r["code"] in existing_pending:
                    pending_skipped += 1
                    continue
                if not dry_run:
                    db.add(PendingOperation(
                        raw_code=r["code"],
                        raw_product_col=r["product_col"] or None,
                        name=normalize_unicode(r["name"]) or r["name"],
                        rate=parse_rate(r["rate"]),
                        component=(p["component"] or None),
                        sequence=p["seq"],
                        side=(p["side"] or None),
                        guessed_stage_id=stage_id,
                        suggested_part=p["product"],  # code-prefix guess, if any
                    ))
                existing_pending.add(r["code"])
                pending_added += 1
                continue

            product_id = part_to_id[final_part]
            if skip_existing and (product_id, r["code"]) in existing_pairs:
                skipped += 1
                continue

            if stage_id is None:
                stage_unknown += 1

            if dry_run:
                added += 1
                continue

            db.add(Operation(
                product_id=product_id,
                stage_id=stage_id,
                code=r["code"],
                name=normalize_unicode(r["name"]) or r["name"],
                rate=parse_rate(r["rate"]),
                sequence=p["seq"],
                component=(p["component"] or None),
                side=(p["side"] or None),
            ))
            existing_pairs.add((product_id, r["code"]))
            added += 1

        if not dry_run:
            db.commit()

    print("\n=========== IMPORT OPERATIONS ===========")
    print(f"rows in CSV              : {len(rows)}")
    print(f"operations {'WOULD ADD' if dry_run else 'added    '}     : {added}")
    print(f"operations skipped (exist): {skipped}")
    print(f"  of added, stage unguessed (stage_id NULL): {stage_unknown}")
    print(f"unmapped -> pending_operations {'(would add)' if dry_run else 'added'}: {pending_added}")
    print(f"  pending skipped (already staged): {pending_skipped}")
    print(f"total unmapped this run  : {unresolved}")
    if unresolved_keys:
        print("\n-- top unresolved (product_col, component) — map by hand --")
        for (pc, comp), n in sorted(unresolved_keys.items(), key=lambda kv: -kv[1])[:12]:
            print(f"   {pc:24} comp={comp:8} ({n} ops)")
    print()


def main():
    parser = argparse.ArgumentParser(description="Import operations from job-list.csv")
    default_csv = SERVER_DIR.parent / "new-data" / "job-list.csv"
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
