#!/usr/bin/env python3
"""
Find BOM vs Products mismatches: product codes in BOM but not in products CSV, and vice versa.

Run from project root:
    cd server && python -m scripts.find_bom_product_mismatches

Or with explicit paths:
    cd server && python -m scripts.find_bom_product_mismatches \\
        --products ../data/products.csv \\
        --bom ../data/bom-detail.csv

Output:
    - In BOM but NOT in products: product codes that appear in bom-detail.csv but not in products.csv
    - In products but NOT in BOM: product codes that appear in products.csv but not in bom-detail.csv
"""

import argparse
import csv
import sys
from pathlib import Path

# Add server to path so we can run as module
SERVER_DIR = Path(__file__).resolve().parent.parent
PROJECT_ROOT = SERVER_DIR.parent


def load_products_part_nos(csv_path: Path) -> set[str]:
    """Load unique Part No. values from products.csv."""
    part_nos = set()
    with open(csv_path, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            part_no = (row.get("Part No.") or row.get("part_no") or "").strip()
            if part_no:
                part_nos.add(part_no)
    return part_nos


def load_bom_product_part_nos(csv_path: Path) -> set[str]:
    """Load unique Product (Part No.) values from bom-detail.csv."""
    part_nos = set()
    with open(csv_path, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            part_no = (
                row.get("Product (Part No.)")
                or row.get("Product")
                or row.get("product")
                or ""
            ).strip()
            if part_no:
                part_nos.add(part_no)
    return part_nos


def main():
    parser = argparse.ArgumentParser(
        description="Find BOM vs Products mismatches (product codes in one but not the other)"
    )
    parser.add_argument(
        "--products",
        type=Path,
        default=PROJECT_ROOT / "data" / "products.csv",
        help="Path to products CSV",
    )
    parser.add_argument(
        "--bom",
        type=Path,
        default=PROJECT_ROOT / "data" / "bom-detail.csv",
        help="Path to BOM detail CSV",
    )
    args = parser.parse_args()

    if not args.products.exists():
        print(f"Products CSV not found: {args.products}")
        sys.exit(1)
    if not args.bom.exists():
        print(f"BOM CSV not found: {args.bom}")
        sys.exit(1)

    products_part_nos = load_products_part_nos(args.products)
    bom_part_nos = load_bom_product_part_nos(args.bom)

    in_bom_not_products = sorted(bom_part_nos - products_part_nos)
    in_products_not_bom = sorted(products_part_nos - bom_part_nos)

    print(f"Products CSV: {len(products_part_nos)} unique part numbers")
    print(f"BOM CSV: {len(bom_part_nos)} unique product part numbers")
    print()

    print("--- In BOM but NOT in Products CSV ---")
    if in_bom_not_products:
        for p in in_bom_not_products:
            print(f"  {p}")
        print(f"  Total: {len(in_bom_not_products)}")
    else:
        print("  (none)")

    print()
    print("--- In Products CSV but NOT in BOM ---")
    if in_products_not_bom:
        for p in in_products_not_bom:
            print(f"  {p}")
        print(f"  Total: {len(in_products_not_bom)}")
    else:
        print("  (none)")


if __name__ == "__main__":
    main()
