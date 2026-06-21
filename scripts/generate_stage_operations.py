#!/usr/bin/env python3
"""
Generate the missing cutting + finishing operations, and fix the stitching stage.

The CSV operations are ALL stitching. Cutting and finishing have no operations, which is a
problem because (a) a stage's BOM is consumed when an operation at that stage happens, and
(b) cutting/finishing labor needs to be paid. So for every product that has a BOM at a stage,
we add one operation for that stage to serve as the trigger.

Three steps (all idempotent):
  1. Set every existing operation's stage -> stitching (CSV ops are all stitching; the import's
     keyword stage-guess was unreliable). This includes unmapped ops (product_id NULL).
     Generated ops (code endswith -CUT / -FIN) are left alone.
  2. For each product with cutting BOM and no cutting op  -> add a cutting op  (rate default 10).
  3. For each product with finishing BOM and no finishing op -> add a finishing op (rate default 0).

Rates are placeholders the client will edit in-app.

Run from server/ :
    python -m scripts.generate_stage_operations --dry-run
    python -m scripts.generate_stage_operations
    python -m scripts.generate_stage_operations --cutting-rate 12 --finishing-rate 0
"""

import argparse
import sys
from decimal import Decimal
from pathlib import Path

SERVER_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SERVER_DIR))

from dotenv import load_dotenv

load_dotenv(SERVER_DIR / ".env")

from sqlalchemy import select, update, insert, func

from app.core.db.engine import SessionLocal
from app.modules.stages.models import Stage
from app.modules.products.models import Product
from app.modules.bom.models import BOMLine
from app.modules.operations.models import Operation

CUT_SUFFIX = "-CUT"
FIN_SUFFIX = "-FIN"


def products_with_bom_at(db, stage_id):
    """{product_id: part_no} for products that have at least one bom_line at this stage."""
    rows = db.execute(
        select(Product.id, Product.part_no)
        .join(BOMLine, BOMLine.product_id == Product.id)
        .where(BOMLine.stage_id == stage_id, BOMLine.deleted_at.is_(None),
               Product.deleted_at.is_(None))
        .distinct()
    ).all()
    return {pid: pn for (pid, pn) in rows}


def products_with_generated_op(db, suffix):
    """Products that already have a generated op (code endswith -CUT / -FIN).

    Idempotency is keyed on the generated code, NOT the stage: step 1 reassigns the
    mislabeled stage ops to stitching, so a stage-based check would wrongly skip products.
    """
    return {
        pid for (pid,) in db.execute(
            select(Operation.product_id).where(
                Operation.code.like(f"%{suffix}"), Operation.deleted_at.is_(None)
            ).distinct()
        ).all()
    }


def run(dry_run: bool, cutting_rate: Decimal, finishing_rate: Decimal):
    with SessionLocal() as db:
        stages = {n.lower(): i for (n, i) in db.execute(  # case-insensitive (DB names are UPPER)
            select(Stage.name, Stage.id).where(Stage.deleted_at.is_(None))
        ).all()}
        cut_id, stitch_id, fin_id = stages["cutting"], stages["stitching"], stages["finishing"]

        # --- Step 1: force non-generated ops -> stitching (incl. unmapped, product_id NULL) ---
        to_stitching = db.execute(
            select(func.count()).select_from(Operation).where(
                Operation.deleted_at.is_(None),
                ~Operation.code.like(f"%{CUT_SUFFIX}"),
                ~Operation.code.like(f"%{FIN_SUFFIX}"),
            )
        ).scalar()

        # --- Steps 2 & 3: which products need a cutting / finishing op ---
        cut_products = products_with_bom_at(db, cut_id)
        fin_products = products_with_bom_at(db, fin_id)
        have_cut = products_with_generated_op(db, CUT_SUFFIX)
        have_fin = products_with_generated_op(db, FIN_SUFFIX)
        need_cut = {pid: pn for pid, pn in cut_products.items() if pid not in have_cut}
        need_fin = {pid: pn for pid, pn in fin_products.items() if pid not in have_fin}

        if not dry_run:
            # Step 1
            db.execute(
                update(Operation)
                .where(~Operation.code.like(f"%{CUT_SUFFIX}"),
                       ~Operation.code.like(f"%{FIN_SUFFIX}"),
                       Operation.deleted_at.is_(None))
                .values(stage_id=stitch_id)
            )
            # Steps 2 & 3
            cut_rows = [{
                "product_id": pid, "stage_id": cut_id, "code": f"{pn}{CUT_SUFFIX}",
                "name": "Cutting", "rate": cutting_rate, "sequence": 0,
            } for pid, pn in need_cut.items()]
            fin_rows = [{
                "product_id": pid, "stage_id": fin_id, "code": f"{pn}{FIN_SUFFIX}",
                "name": "Finishing", "rate": finishing_rate, "sequence": 99,
            } for pid, pn in need_fin.items()]
            for rows in (cut_rows, fin_rows):
                if rows:
                    db.execute(insert(Operation).values(rows))
            db.commit()

    print("\n=========== GENERATE STAGE OPERATIONS ===========")
    print(f"Step 1 — operations set -> stitching : {to_stitching}")
    print(f"Step 2 — cutting ops to add (@ {cutting_rate}) : {len(need_cut)}")
    print(f"Step 3 — finishing ops to add (@ {finishing_rate}): {len(need_fin)}")
    print(f"{'(dry run — nothing written)' if dry_run else 'committed.'}")
    print()


def main():
    ap = argparse.ArgumentParser(description="Generate cutting/finishing ops + fix stitching stage")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--cutting-rate", type=Decimal, default=Decimal("10"))
    ap.add_argument("--finishing-rate", type=Decimal, default=Decimal("0"))
    args = ap.parse_args()
    if args.dry_run:
        print("(dry run — no changes will be made)")
    run(args.dry_run, args.cutting_rate, args.finishing_rate)


if __name__ == "__main__":
    main()
