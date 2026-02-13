"""
Raw SQL playground. Edit QUERY below and run from server root:

    python -m app.core.db.playground

Or from server directory:

    cd server && python -m app.core.db.playground
"""

from sqlalchemy import text
from app.core.db.engine import SessionLocal

# --- Edit your SQL here ---
QUERY = """
SELECT
    rm.name AS material,
    bl.raw_qty AS needed_for_batch,
    bl.batch_qty AS batch_size,
    (bl.raw_qty / bl.batch_qty * 100) AS needed_for_100_units,
    rm.stock_qty AS current_stock,
    CASE
        WHEN rm.stock_qty >= (bl.raw_qty / bl.batch_qty * 100)
        THEN 'In Stock'
        ELSE 'Need to Order'
    END AS status,
    CASE
        WHEN rm.stock_qty < (bl.raw_qty / bl.batch_qty * 100)
        THEN ((bl.raw_qty / bl.batch_qty * 100) - rm.stock_qty)
        ELSE 0
    END AS shortage
FROM bom_lines bl
JOIN products p ON bl.product_id = p.id
JOIN raw_materials rm ON bl.raw_material_id = rm.id
WHERE p.part_no = 'A001'
  AND bl.variant = 'BLACK';
"""

QUERY = """
select count(*) from bom_lines;
"""

def run():
    with SessionLocal() as session:
        result = session.execute(text(QUERY))
        session.commit()
        if result.returns_rows:
            rows = result.fetchall()
            columns = list(result.keys())
            print("Columns:", columns)
            print("Rows:", len(rows))
            for row in rows:
                print(dict(row._mapping) if hasattr(row, "_mapping") else row)
        else:
            print("Done (no result set).")


if __name__ == "__main__":
    run()
