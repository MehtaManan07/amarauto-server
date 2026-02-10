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
SELECT DISTINCT unit_type FROM raw_materials;
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
