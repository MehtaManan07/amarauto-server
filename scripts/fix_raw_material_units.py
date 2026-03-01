#!/usr/bin/env python3
"""
Fix raw materials with unit_type 'unknown' by updating from data/raw-materials.csv.

Run from project root:
    cd server && python -m scripts.fix_raw_material_units

Options:
    --csv PATH   Path to CSV (default: ../data/raw-materials.csv)
    --dry-run    Print what would be updated without writing to DB
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

from app.core.db.engine import SessionLocal
from app.core.utils import normalize_unicode
from app.modules.raw_materials.models import RawMaterial


def normalize_name(s: str) -> str:
    """Normalize name for matching: strip, uppercase, handle quotes."""
    if not s:
        return ""
    s = str(s).strip().upper()
    # Remove surrounding quotes that CSV might have
    if s.startswith('"') and s.endswith('"'):
        s = s[1:-1]
    return s


def normalize_unit(unit: str) -> str:
    """Normalize unit type: PC, MTR, KG, SET, ROLL, etc."""
    if not unit or not str(unit).strip():
        return ""
    u = str(unit).strip().upper()
    # Common variants
    if u in ("MTR", "M", "METRE", "METRES", "METER", "METERS"):
        return "MTR"
    if u in ("KG", "KGS", "KILO", "KILOGRAM", "KILOGRAMS"):
        return "KG"
    if u in ("PC", "PCS", "PCE", "PIECE", "PIECES", "NO", "NOS"):
        return "PC"
    if u in ("SET", "SETS"):
        return "SET"
    if u in ("ROLL", "ROLLS"):
        return "ROLL"
    return u


def load_csv_units(csv_path: Path) -> dict[str, str]:
    """Load CSV and return mapping of normalized name -> normalized unit_type."""
    mapping = {}
    with open(csv_path, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        headers = reader.fieldnames or []
        # Find columns: "Name", "Unit Type" (or similar)
        name_col = next((h for h in headers if h.strip().lower() == "name"), headers[0] if headers else None)
        unit_col = next(
            (h for h in headers if "unit" in h.lower() and "type" in h.lower()),
            next((h for h in headers if "unit" in h.lower()), None),
        )

        for row in reader:
            name = (row.get(name_col) or "").strip() if name_col else ""
            unit = (row.get(unit_col) or "").strip() if unit_col else ""
            if name and unit:
                mapping[normalize_name(name)] = normalize_unit(unit)

    return mapping


def run_fix(csv_path: Path, dry_run: bool) -> tuple[int, int]:
    """Fix raw materials with unknown unit. Returns (updated, not_found)."""
    mapping = load_csv_units(csv_path)
    if not mapping:
        print("No name->unit mappings found in CSV. Check CSV format.")
        return 0, 0

    updated = 0
    not_found = 0

    with SessionLocal() as db:
        # Find all raw materials with unit_type = 'unknown' (case-insensitive)
        stmt = select(RawMaterial).where(
            RawMaterial.deleted_at.is_(None),
            RawMaterial.unit_type.ilike("unknown"),
        )
        rows = db.execute(stmt).scalars().all()

        for rm in rows:
            key = normalize_name(rm.name)
            new_unit = mapping.get(key)
            if new_unit:
                if dry_run:
                    print(f"Would update: {rm.name!r} unit_type {rm.unit_type!r} -> {new_unit!r}")
                else:
                    rm.unit_type = new_unit
                updated += 1
            else:
                print(f"Not found in CSV: {rm.name!r} (id={rm.id})")
                not_found += 1

        if not dry_run and updated > 0:
            db.commit()

    return updated, not_found


def main():
    parser = argparse.ArgumentParser(description="Fix raw materials with unit_type 'unknown' from CSV")
    parser.add_argument(
        "--csv",
        type=Path,
        default=Path(__file__).resolve().parent.parent.parent / "data" / "raw-materials.csv",
        help="Path to raw materials CSV",
    )
    parser.add_argument("--dry-run", action="store_true", help="Print changes without writing")
    args = parser.parse_args()

    if not args.csv.exists():
        print(f"CSV not found: {args.csv}")
        sys.exit(1)

    print(f"Loading units from {args.csv}")
    updated, not_found = run_fix(args.csv, args.dry_run)

    if args.dry_run:
        print(f"\n[DRY RUN] Would update {updated} raw materials")
    else:
        print(f"\nUpdated {updated} raw materials")
    if not_found:
        print(f"Not found in CSV: {not_found}")


if __name__ == "__main__":
    main()
