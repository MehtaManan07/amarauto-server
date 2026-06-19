"""
Sync a local SQLite copy of the Turso DB for fast offline dev.

Turso is in us-east; from elsewhere every query is a ~1s round-trip, so the app feels
sluggish in local dev. This pulls a full local replica (server/local_dev.db). Run the app
against it with USE_LOCAL_DB=1 (see `make run-local`) — reads/writes are instant and never
touch prod.

Run from server/ :
    python -m scripts.sync_local_db
"""

import sys
from pathlib import Path

SERVER_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SERVER_DIR))

from dotenv import load_dotenv

load_dotenv(SERVER_DIR / ".env")

import libsql_experimental as libsql
from app.core.config import config

dest = SERVER_DIR / "local_dev.db"
print(f"Syncing Turso -> {dest} ...")
conn = libsql.connect(str(dest), sync_url=config.turso_database_url, auth_token=config.turso_auth_token)
conn.sync()
print(f"Done. {dest.stat().st_size:,} bytes. Run the app with: make run-local")
