"""
Seed / tear down an ISOLATED TEST sandbox in the prod Turso DB.

Lets you exercise the whole production flow (create batch -> move through stages
-> consume BOM -> log work) without touching real business data: every row it
creates is TEST-prefixed (raw materials/products by name/part_no, batches by
batch_no, operations/BOM by their TEST product). It REUSES the existing 4 stages
(CUTTING/STITCHING/FINISHING/ASSEMBLY) rather than adding board columns.

Because test products consume only TEST raw materials, real stock is never
touched. Teardown removes every test row (and restores stock for any
consumption, in case a test batch ever consumed a real material).

Usage (from server/):
    python -m scripts.seed_test_data seed
    python -m scripts.seed_test_data teardown
"""

import argparse
from decimal import Decimal
from datetime import datetime

from sqlalchemy import select, delete, or_

from app.core.db.engine import SessionLocal
from app.modules.stages.models import Stage
from app.modules.products.models import Product
from app.modules.raw_materials.models import RawMaterial
from app.modules.bom.models import BOMLine
from app.modules.operations.models import Operation
from app.modules.work_logs.models import WorkLog
from app.modules.production.models import (
    Batch, BatchMovement, BatchReject, MaterialConsumption,
    BATCH_OPEN, BATCH_IN_PROGRESS,
)

PREFIX = "TEST-"

# --- the sandbox spec --------------------------------------------------------
RAW_MATERIALS = [  # (name, unit_type, stock_qty)
    ("TEST-FABRIC", "m", 100000),
    ("TEST-FOAM", "sheet", 100000),
    ("TEST-THREAD", "cone", 100000),
    ("TEST-ZIPPER", "pc", 100000),
    ("TEST-LABEL", "pc", 100000),
]
PRODUCTS = [  # (part_no, name)
    ("TEST-P1", "TEST Car Seat Cover"),
    ("TEST-P2", "TEST Neck Pillow"),
]
# product part_no -> [(stage_name, raw_material_name, qty_per_batch)]  (batch_size = 1)
BOM = {
    "TEST-P1": [
        ("CUTTING", "TEST-FABRIC", 3), ("CUTTING", "TEST-FOAM", 2),
        ("STITCHING", "TEST-THREAD", 1),
        ("FINISHING", "TEST-LABEL", 1),
        ("ASSEMBLY", "TEST-ZIPPER", 1),
    ],
    "TEST-P2": [  # skips FINISHING — exercises the "advance to next stage with a recipe" path
        ("CUTTING", "TEST-FABRIC", 2),
        ("STITCHING", "TEST-THREAD", 1),
        ("ASSEMBLY", "TEST-ZIPPER", 1),
    ],
}
# product part_no -> [(stage_name, code, name, rate)]
OPERATIONS = {
    "TEST-P1": [("CUTTING", "TCUT1", "Test cut", 5), ("STITCHING", "TSTITCH1", "Test stitch", 8),
                ("FINISHING", "TFINISH1", "Test finish", 4), ("ASSEMBLY", "TASSEM1", "Test assemble", 6)],
    "TEST-P2": [("CUTTING", "TCUT2", "Test cut", 5), ("STITCHING", "TSTITCH2", "Test stitch", 8),
                ("ASSEMBLY", "TASSEM2", "Test assemble", 6)],
}
# parked batches (movement-only, no consumption) so the board has draggable cards
BATCHES = [("TEST-P1", "CUTTING"), ("TEST-P2", "STITCHING")]  # (product part_no, parked_at_stage)
BATCH_QTY = Decimal("10")


def _active_stages(db):
    return list(db.execute(
        select(Stage).where(Stage.deleted_at.is_(None)).order_by(Stage.sequence)
    ).scalars().all())


def teardown(db, verbose=True):
    """Delete every TEST row (children -> parents), restoring any consumed stock first."""
    prod_ids = db.execute(select(Product.id).where(Product.part_no.like(f"{PREFIX}%"))).scalars().all()
    rm_ids = db.execute(select(RawMaterial.id).where(RawMaterial.name.like(f"{PREFIX}%"))).scalars().all()
    batches = db.execute(select(Batch).where(Batch.batch_no.like(f"{PREFIX}%"))).scalars().all()
    # SAFETY: refuse if anything without the test prefix slipped into the batch match.
    assert all(b.batch_no.startswith(PREFIX) for b in batches), "refusing: a non-test batch matched"
    batch_ids = [b.id for b in batches]
    op_ids = (db.execute(select(Operation.id).where(Operation.product_id.in_(prod_ids))).scalars().all()
              if prod_ids else [])

    # Restore stock for any consumption tied to test batches (covers the edge case of a
    # test batch consuming a REAL material; test materials get deleted below anyway).
    if batch_ids:
        for c in db.execute(select(MaterialConsumption).where(MaterialConsumption.batch_id.in_(batch_ids))).scalars():
            if c.qty_consumed is None:
                continue
            rm = db.get(RawMaterial, c.raw_material_id)
            if rm is not None:
                rm.stock_qty = (rm.stock_qty or Decimal("0")) + c.qty_consumed
        db.flush()

    # Delete children first so no FK is left dangling.
    if batch_ids or op_ids:
        conds = []
        if batch_ids:
            conds.append(WorkLog.batch_id.in_(batch_ids))
        if op_ids:
            conds.append(WorkLog.operation_id.in_(op_ids))
        db.execute(delete(WorkLog).where(or_(*conds)))
    if batch_ids:
        db.execute(delete(MaterialConsumption).where(MaterialConsumption.batch_id.in_(batch_ids)))
        db.execute(delete(BatchMovement).where(BatchMovement.batch_id.in_(batch_ids)))
        db.execute(delete(BatchReject).where(BatchReject.batch_id.in_(batch_ids)))
        db.execute(delete(Batch).where(Batch.id.in_(batch_ids)))
    if prod_ids:
        db.execute(delete(Operation).where(Operation.product_id.in_(prod_ids)))
        db.execute(delete(BOMLine).where(BOMLine.product_id.in_(prod_ids)))
        db.execute(delete(Product).where(Product.id.in_(prod_ids)))
    if rm_ids:
        db.execute(delete(RawMaterial).where(RawMaterial.id.in_(rm_ids)))
    db.commit()
    if verbose:
        print(f"teardown: removed {len(prod_ids)} product(s), {len(rm_ids)} raw material(s), "
              f"{len(op_ids)} operation(s), {len(batches)} batch(es), + their BOM/worklogs/ledger.")
    return len(prod_ids) + len(rm_ids) + len(batches)


def seed(db, verbose=True):
    """Create the full TEST sandbox (idempotent: clears any prior TEST data first)."""
    teardown(db, verbose=False)

    stages = {s.name: s for s in _active_stages(db)}
    needed = ({n for spec in BOM.values() for (n, _, _) in spec}
              | {n for spec in OPERATIONS.values() for (n, _, _, _) in spec}
              | {n for _, n in BATCHES})
    absent = needed - set(stages)
    if absent:
        print(f"seed: required stages not found in prod: {sorted(absent)}; aborting.")
        return 0
    now = datetime.utcnow()

    rm_by_name = {}
    for name, unit, stock in RAW_MATERIALS:
        rm = RawMaterial(name=name, unit_type=unit, stock_qty=Decimal(str(stock)),
                         created_at=now, updated_at=now)
        db.add(rm)
        rm_by_name[name] = rm

    prod_by_partno = {}
    for part_no, name in PRODUCTS:
        p = Product(part_no=part_no, name=name, is_manufactured=True, is_active=True,
                    created_at=now, updated_at=now)
        db.add(p)
        prod_by_partno[part_no] = p
    db.flush()  # assign rm/product ids

    bom_n = 0
    for part_no, lines in BOM.items():
        for stage_name, rm_name, qty in lines:
            db.add(BOMLine(product_id=prod_by_partno[part_no].id, stage_id=stages[stage_name].id,
                           raw_material_id=rm_by_name[rm_name].id, colour=None,
                           batch_size=Decimal("1"), qty_per_batch=Decimal(str(qty)),
                           created_at=now, updated_at=now))
            bom_n += 1

    op_n = 0
    for part_no, ops in OPERATIONS.items():
        for i, (stage_name, code, oname, rate) in enumerate(ops):
            db.add(Operation(product_id=prod_by_partno[part_no].id, stage_id=stages[stage_name].id,
                             code=code, name=oname, rate=Decimal(str(rate)), sequence=i + 1,
                             created_at=now, updated_at=now))
            op_n += 1

    ordered = sorted(stages.values(), key=lambda s: s.sequence)
    first = ordered[0]
    for i, (part_no, parked_name) in enumerate(BATCHES):
        target = stages[parked_name]
        b = Batch(batch_no=f"{PREFIX}{i + 1}", product_id=prod_by_partno[part_no].id, colour=None,
                  quantity=BATCH_QTY, status=BATCH_OPEN if target.id == first.id else BATCH_IN_PROGRESS,
                  created_at=now, updated_at=now)
        db.add(b)
        db.flush()
        db.add(BatchMovement(batch_id=b.id, from_stage_id=None, to_stage_id=first.id,
                             quantity=BATCH_QTY, created_at=now, updated_at=now))
        prev = first
        for s in ordered[1:]:
            if prev.sequence >= target.sequence:
                break
            db.add(BatchMovement(batch_id=b.id, from_stage_id=prev.id, to_stage_id=s.id,
                                 quantity=BATCH_QTY, created_at=now, updated_at=now))
            prev = s
    db.commit()
    if verbose:
        print("seed: created TEST sandbox (real stock untouched):")
        print(f"  raw materials {len(RAW_MATERIALS)}  products {len(PRODUCTS)}  "
              f"bom lines {bom_n}  operations {op_n}  parked batches {len(BATCHES)}")
        print("  Test the whole flow on TEST-P1 / TEST-P2: create a batch, move it through the")
        print("  stages (drag on the board) — consumption hits only TEST-* materials.")
        print("  Run 'teardown' to remove everything.")
    return 1


def main():
    ap = argparse.ArgumentParser(description="Seed/teardown an isolated TEST sandbox in the prod DB.")
    ap.add_argument("action", choices=["seed", "teardown"])
    args = ap.parse_args()
    db = SessionLocal()
    try:
        seed(db) if args.action == "seed" else teardown(db)
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
