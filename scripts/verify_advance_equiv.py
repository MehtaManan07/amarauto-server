"""
Empirical proof that the two `advance` optimizations are behavior-preserving.

Runs entirely inside ONE transaction that is ROLLED BACK at the end — it never
commits, so it mutates no data (safe even against local_dev.db). Synthesises its
own batch + ledger so it doesn't depend on what's in the DB.

Proves:
  1. WIP delta == re-derivation. For a single (from -> to, qty) movement, applying
     the in-memory delta (-qty at from, +qty at to) yields EXACTLY the same WIP as
     re-running _wip_by_stage against the ledger after the insert. Tested across
     many (from, to, qty) combinations on a non-trivial ledger (intake + partial
     moves + a reject).
  2. _detail is output-identical whether handed the pre-computed delta WIP or left
     to re-derive (same wip lines, same current_stage).
  3. Fix 2: the batched IN-read returns the SAME identity-mapped RawMaterial objects
     that db.get would return (so mutating stock still emits the same UPDATE).

Run:  USE_LOCAL_DB=1 python -m scripts.verify_advance_equiv
"""

import os
os.environ.setdefault("USE_LOCAL_DB", "1")  # never touch Turso

from decimal import Decimal
from datetime import datetime

from sqlalchemy import select

from app.core.db.engine import SessionLocal
from app.modules.production.service import (
    _wip_by_stage, _active_stages, _detail, _stage_bom_rows, _aggregate_materials,
)
from app.modules.production.models import Batch, BatchMovement, BatchReject
from app.modules.products.models import Product
from app.modules.stages.models import Stage
from app.modules.raw_materials.models import RawMaterial

ZERO = Decimal("0")
PASS, FAIL = "\033[32mPASS\033[0m", "\033[31mFAIL\033[0m"


def wip_str(w):
    return "{" + ", ".join(f"{k}:{v}" for k, v in sorted(w.items())) + "}"


def main() -> int:
    sess = SessionLocal()
    failures = 0
    checks = 0
    try:
        stages = _active_stages(sess)
        if len(stages) < 2:
            print("need >=2 active stages to test; aborting (no data changed).")
            return 0
        product = sess.execute(select(Product).limit(1)).scalars().first()
        if product is None:
            print("need >=1 product for the synthetic batch FK; aborting.")
            return 0

        s0, s1 = stages[0], stages[1]
        s2 = stages[2] if len(stages) > 2 else stages[1]

        # --- synthesise a batch with a NON-TRIVIAL ledger (rolled back later) -----
        batch = Batch(batch_no="__VERIFY_TMP__", product_id=product.id,
                      quantity=Decimal("100.00"), status="in_progress")
        sess.add(batch)
        sess.flush()  # assign batch.id (uncommitted)

        # intake 100 @ s0; move 40 -> s1; reject 5 @ s0  -> a realistic, mixed ledger
        sess.add_all([
            BatchMovement(batch_id=batch.id, from_stage_id=None, to_stage_id=s0.id, quantity=Decimal("100.00")),
            BatchMovement(batch_id=batch.id, from_stage_id=s0.id, to_stage_id=s1.id, quantity=Decimal("40.00")),
            BatchReject(batch_id=batch.id, stage_id=s0.id, quantity=Decimal("5.00")),
        ])
        sess.flush()

        base_wip = _wip_by_stage(sess, batch.id)
        print(f"synthetic ledger -> WIP {wip_str(base_wip)}  (s0={s0.id}, s1={s1.id}, s2={s2.id})\n")

        # --- PROOF 1: delta == re-derivation, across many (from,to,qty) combos ----
        combos = [
            (s0.id, s1.id, Decimal("10.00")),
            (s0.id, s1.id, Decimal("55.00")),   # full remaining at s0 (95 waiting)
            (s1.id, s2.id, Decimal("40.00")),   # full move s1 -> s2
            (s1.id, s2.id, Decimal("0.01")),    # tiny fractional
            (s0.id, s2.id, Decimal("33.33")),   # skip a stage, fractional
        ]
        for from_sid, to_sid, qty in combos:
            if from_sid == to_sid:
                continue
            wip = _wip_by_stage(sess, batch.id)  # pre-move (re-read each time)

            # (a) in-memory delta exactly as advance() computes it
            wip_delta = dict(wip)
            wip_delta[from_sid] = (wip_delta.get(from_sid) or ZERO) - qty
            wip_delta[to_sid] = (wip_delta.get(to_sid) or ZERO) + qty

            # (b) actually insert the movement, re-derive from the ledger, then undo it
            mv = BatchMovement(batch_id=batch.id, from_stage_id=from_sid,
                               to_stage_id=to_sid, quantity=qty)
            sess.add(mv)
            sess.flush()
            wip_rederive = _wip_by_stage(sess, batch.id)

            # compare across the union of ALL stage ids (treat missing as 0)
            all_sids = set(wip_delta) | set(wip_rederive) | {s.id for s in stages}
            mismatch = [
                (sid, wip_delta.get(sid) or ZERO, wip_rederive.get(sid) or ZERO)
                for sid in all_sids
                if (wip_delta.get(sid) or ZERO) != (wip_rederive.get(sid) or ZERO)
            ]
            checks += 1
            ok = not mismatch
            failures += 0 if ok else 1
            print(f"[{PASS if ok else FAIL}] move {qty} {from_sid}->{to_sid}: "
                  f"delta {wip_str(wip_delta)} vs ledger {wip_str(wip_rederive)}"
                  + ("" if ok else f"  MISMATCH {mismatch}"))

            # PROOF 2: _detail identical with passed delta vs re-derivation (still flushed)
            product_obj = sess.get(Product, batch.product_id)
            d_delta = _detail(sess, batch, product_obj, stages, wip=wip_delta)
            d_fresh = _detail(sess, batch, product_obj, stages, wip=None)
            lines_delta = {l.stage_id: l.waiting for l in d_delta.wip}
            lines_fresh = {l.stage_id: l.waiting for l in d_fresh.wip}
            d_ok = (lines_delta == lines_fresh
                    and d_delta.current_stage_id == d_fresh.current_stage_id)
            checks += 1
            failures += 0 if d_ok else 1
            print(f"      [{PASS if d_ok else FAIL}] _detail parity: "
                  f"current_stage {d_delta.current_stage_id} vs {d_fresh.current_stage_id}, "
                  f"wip lines {'equal' if lines_delta == lines_fresh else 'DIFFER'}")

            sess.delete(mv)  # undo this combo's movement before the next
            sess.flush()

        # --- PROOF 3: batched IN-read returns the SAME instances as db.get ---------
        # This is the property Fix 2 relies on: select(...).where(id.in_(...)) and
        # db.get(id) yield the identical session-tracked object, so `rm.stock_qty = new`
        # produces the same UPDATE either way. Sample real raw materials directly.
        rm_ids = sess.execute(
            select(RawMaterial.id).where(RawMaterial.deleted_at.is_(None)).limit(50)
        ).scalars().all()
        identity_ok = True
        if rm_ids:
            by_id = {
                rm.id: rm for rm in sess.execute(
                    select(RawMaterial).where(RawMaterial.id.in_(rm_ids))
                ).scalars().all()
            }
            for rm_id in rm_ids:
                if sess.get(RawMaterial, rm_id) is not by_id.get(rm_id):
                    identity_ok = False
        checks += 1
        failures += 0 if identity_ok else 1
        if rm_ids:
            print(f"\n[{PASS if identity_ok else FAIL}] batched-read identity: "
                  f"{len(rm_ids)} materials — IN-query objects ARE the db.get objects "
                  f"(same UPDATE on flush)")
        else:
            print("\n[skip] no raw materials in DB to sample for Proof 3")

        print(f"\n{checks} checks, {failures} failures.")
        return 1 if failures else 0
    finally:
        sess.rollback()  # <-- nothing is ever committed
        sess.close()
        print("rolled back — no data changed.")


if __name__ == "__main__":
    raise SystemExit(main())
