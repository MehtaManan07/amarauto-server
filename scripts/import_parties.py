#!/usr/bin/env python3
"""
Import party data from data/parties.csv or data/cleaned/parties_cleaned.csv into the database.

Run from project root:
    cd server && python -m scripts.import_parties

Or with explicit path to CSV:
    cd server && python -m scripts.import_parties --csv ../data/parties.csv

Options:
    --csv PATH       Path to CSV (default: ../data/cleaned/parties_cleaned.csv)
    --skip-existing  Skip rows where name already exists
    --dry-run        Print what would be imported without writing to DB
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
from app.modules.parties.models import Party


# CSV column name -> Party model field
COLUMN_MAP = {
    "name": "name",
    "email": "email",
    "priorstatename": "state",
    "parent": "party_type",
    "oldaddress": "address_line_1",
    "oldpincode": "pin_code",
    "ledgerphone": "phone",
    "ledgerfax": "fax",
    "ledgercontact": "contact_person",
    "ledgermobile": "mobile",
    "partygstin": "gstin",
    "address2": "address_line_2",
    "address3": "address_line_3",
    "address4": "address_line_4",
    "address5": "address_line_5",
}


def normalize_header(h: str) -> str:
    """Strip $ and _ from header, lowercase for lookup."""
    return h.strip().lstrip("$_").lower().replace(" ", "")


def load_csv(csv_path: Path) -> list[dict]:
    """Load CSV and return list of dicts with normalized Party model keys."""
    rows = []
    with open(csv_path, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        raw_headers = reader.fieldnames or []
        # Build header -> model field map
        header_map = {}
        for h in raw_headers:
            norm = normalize_header(h)
            if norm in COLUMN_MAP:
                header_map[h] = COLUMN_MAP[norm]

        for row in reader:
            out = {}
            for raw_key, model_key in header_map.items():
                val = row.get(raw_key, "").strip() if row.get(raw_key) else ""
                if val:
                    out[model_key] = normalize_unicode(val) or val
                else:
                    out[model_key] = None
            name = out.get("name")
            if not name:
                continue
            rows.append(out)
    return rows


def run_import(csv_path: Path, skip_existing: bool, dry_run: bool) -> tuple[int, int, int]:
    """Import parties. Returns (added, skipped, errors)."""
    rows = load_csv(csv_path)
    if not rows:
        print("No rows found in CSV.")
        return 0, 0, 0

    added = 0
    skipped = 0
    errors = 0

    with SessionLocal() as db:
        for row in rows:
            name = row.get("name")
            if not name:
                continue

            if skip_existing:
                existing = db.execute(
                    select(Party).where(
                        Party.name == name,
                        Party.deleted_at.is_(None),
                    )
                ).scalar_one_or_none()
                if existing:
                    skipped += 1
                    continue

            if dry_run:
                added += 1
                continue

            try:
                party = Party(**row)
                db.add(party)
                added += 1
            except Exception as e:
                print(f"  ERROR: {name}: {e}")
                errors += 1

        if not dry_run:
            db.commit()

    return added, skipped, errors


def main():
    parser = argparse.ArgumentParser(description="Import parties from CSV")
    default_csv = (
        Path(__file__).resolve().parent.parent.parent
        / "data"
        / "cleaned"
        / "parties_cleaned.csv"
    )
    parser.add_argument(
        "--csv",
        type=Path,
        default=default_csv,
        help=f"Path to CSV (default: {default_csv})",
    )
    parser.add_argument(
        "--skip-existing",
        action="store_true",
        help="Skip rows where name already exists",
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
        print("(skipping existing names)")

    added, skipped, errors = run_import(args.csv, args.skip_existing, args.dry_run)
    print(f"Done: added={added}, skipped={skipped}, errors={errors}")


if __name__ == "__main__":
    main()
