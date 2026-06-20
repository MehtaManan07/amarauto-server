"""
Seed / tear down TEST production batches in the prod Turso DB.

Single script, two actions (seed | teardown). Test batches are tagged with a
`TEST-` batch_no prefix so teardown targets ONLY them and can never touch real
data (real batches are numbered `B-0001`).

Seeding parks batches at different stages using movements only — it does NOT
consume any raw-material stock — so the board gets draggable cards across the
columns with zero impact on real stock. If you then drag/advance a test batch
while testing, that real move WILL consume stock; teardown reverses it by
restoring every MaterialConsumption row tied to a test batch.

Usage (from server/):
    python -m scripts.seed_test_batches seed
    python -m scripts.seed_test_batches seed --quantity 5
    python -m scripts.seed_test_batches teardown
"""

import argparse
from decimal import Decimal
from datetime import datetime

from sqlalchemy import select, delete

from app.core.db.engine import SessionLocal
from app.modules.stages.models import Stage
from app.modules.products.models import Product
from app.modules.raw_materials.models import RawMaterial
from app.modules.production.models import (
    Batch, BatchMovement, BatchReject, MaterialConsumption,
    BATCH_OPEN, BATCH_IN_PROGRESS,
)

PREFIX = "TEST-"


def _active_stages(db):
    return list(db.execute(
        select(Stage).where(Stage.deleted_at.is_(None)).order_by(Stage.sequence)
    ).scalars().all())


def teardown(db, prefix=PREFIX, verbose=True):
    """Remove all TEST- batches and their ledger rows; restore any consumed stock."""
    batches = db.execute(
        select(Batch).where(Batch.batch_no.like(f"{prefix}%"))
    ).scalars().all()
    # SAFETY: refuse to proceed if anything without the test prefix slipped in.
    assert all(b.batch_no.startswith(prefix) for b in batches), "refusing: a non-test batch matched"
    if not batches:
        if verbose:
            print("teardown: no test batches found — nothing to do.")
        return 0
    ids = [b.id for b in batches]

    # Restore stock consumed by these test batches (reverse each consumption row).
    cons = db.execute(
        select(MaterialConsumption).where(MaterialConsumption.batch_id.in_(ids))
    ).scalars().all()
    restored = 0
    for c in cons:
        if c.qty_consumed is None:
            continue
        rm = db.get(RawMaterial, c.raw_material_id)
        if rm is not None:
            rm.stock_qty = (rm.stock_qty or Decimal("0")) + c.qty_consumed
            restored += 1
    db.flush()  # persist stock restores before deleting the consumption rows

    # Hard-delete the test ledger rows + batches (one bulk statement each; children first).
    db.execute(delete(MaterialConsumption).where(MaterialConsumption.batch_id.in_(ids)))
    db.execute(delete(BatchMovement).where(BatchMovement.batch_id.in_(ids)))
    db.execute(delete(BatchReject).where(BatchReject.batch_id.in_(ids)))
    db.execute(delete(Batch).where(Batch.id.in_(ids)))
    db.commit()
    if verbose:
        print(f"teardown: removed {len(batches)} test batch(es); restored stock on {restored} consumption row(s).")
    return len(batches)


def seed(db, quantity="1", prefix=PREFIX, verbose=True):
    """Create a spread of TEST- batches parked at the first few stages (no stock consumed)."""
    teardown(db, prefix=prefix, verbose=False)  # idempotent: clean slate first

    stages = _active_stages(db)
    if len(stages) < 2:
        print("seed: need >=2 active stages; aborting.")
        return 0
    products = db.execute(
        select(Product).where(Product.deleted_at.is_(None)).order_by(Product.id).limit(8)
    ).scalars().all()
    if not products:
        print("seed: no products to reference; aborting.")
        return 0

    qty = Decimal(str(quantity))
    now = datetime.utcnow()
    # One batch parked at each of the first few stages, so you can drag from different
    # positions (earlier columns dim, later columns light up).
    targets = stages[: min(3, len(stages))]
    created = []
    for i, target in enumerate(targets):
        p = products[i % len(products)]
        b = Batch(
            batch_no=f"{prefix}{i + 1}",
            product_id=p.id,
            style=None,
            colour="TEST",
            quantity=qty,
            status=BATCH_OPEN if target.id == stages[0].id else BATCH_IN_PROGRESS,
            created_at=now, updated_at=now,
        )
        db.add(b)
        db.flush()  # assign b.id
        # Intake into the first stage, then advance (movements only) up to the target.
        db.add(BatchMovement(batch_id=b.id, from_stage_id=None, to_stage_id=stages[0].id,
                             quantity=qty, created_at=now, updated_at=now))
        prev = stages[0]
        for s in stages[1:]:
            if prev.sequence >= target.sequence:
                break
            db.add(BatchMovement(batch_id=b.id, from_stage_id=prev.id, to_stage_id=s.id,
                                 quantity=qty, created_at=now, updated_at=now))
            prev = s
        created.append((b.batch_no, p.part_no, target.name))
    db.commit()
    if verbose:
        print(f"seed: created {len(created)} test batch(es) (qty {qty}, no stock consumed):")
        for bn, pn, stage in created:
            print(f"  {bn:8} {pn:10} @ {stage}")
        print("Drag a card onto a later-stage column to test. Run 'teardown' when done.")
    return len(created)


def main():
    ap = argparse.ArgumentParser(description="Seed/teardown TEST batches in the prod DB.")
    ap.add_argument("action", choices=["seed", "teardown"])
    ap.add_argument("--quantity", default="1", help="units per test batch (seed only)")
    ap.add_argument("--prefix", default=PREFIX, help="batch_no prefix marking test data")
    args = ap.parse_args()

    db = SessionLocal()
    try:
        if args.action == "seed":
            seed(db, quantity=args.quantity, prefix=args.prefix)
        else:
            teardown(db, prefix=args.prefix)
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
