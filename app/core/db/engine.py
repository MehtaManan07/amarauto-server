"""
Turso (libSQL) Database Engine Configuration for FastAPI.

Uses synchronous SQLAlchemy with asyncio.to_thread() for async compatibility.
Thread-safe: entire session lifecycle stays in a single thread.
"""

from typing import TypeVar, Callable
import os
import asyncio
from pathlib import Path

from sqlalchemy import create_engine, text, event
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import QueuePool

from app.core.config import config as settings

T = TypeVar('T')

# --- Local-DB mode (fast offline dev) ----------------------------------------
# Turso lives in us-east; from elsewhere each query is a ~1s round-trip, which
# makes interactive dev painful. Set USE_LOCAL_DB=1 (see `make run-local`) to run
# against a local SQLite copy synced from Turso (scripts/sync_local_db.py).
# Reads/writes are instant and NEVER touch prod. Leave it unset for prod (Turso).
_USE_LOCAL = os.getenv("USE_LOCAL_DB", "").strip().lower() not in ("", "0", "false", "no")

if _USE_LOCAL:
    _local_path = Path(__file__).resolve().parents[3] / "local_dev.db"  # server/local_dev.db
    engine = create_engine(
        f"sqlite:///{_local_path}",
        connect_args={"check_same_thread": False},
        poolclass=QueuePool,
        pool_size=5,
        max_overflow=5,
        pool_timeout=10,
        echo=False,
    )

    @event.listens_for(engine, "connect")
    def _sqlite_wal(dbapi_conn, _rec):  # WAL = better read/write concurrency for the thread pool
        cur = dbapi_conn.cursor()
        cur.execute("PRAGMA journal_mode=WAL")
        cur.close()
else:
    # Build Turso URL: sqlite+libsql://host?secure=true
    # TURSO_DATABASE_URL contains "libsql://host", so we replace the scheme
    turso_url = settings.turso_database_url.replace("libsql://", "sqlite+libsql://") + "?secure=true"

    # Override the libSQL dialect's default SingletonThreadPool (a SQLite legacy
    # default) with QueuePool — Turso is network-backed and benefits from real
    # connection pooling. pool_pre_ping is intentionally omitted (HTTP transport,
    # so pre-ping is wasted bandwidth); pool_recycle guards against long-idle
    # libSQL HTTP streams going stale.
    engine = create_engine(
        turso_url,
        connect_args={"auth_token": settings.turso_auth_token},
        poolclass=QueuePool,
        pool_size=20,
        max_overflow=10,
        pool_recycle=1800,
        pool_timeout=10,
        echo=False,
    )

# Session factory
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)


async def run_db(fn: Callable[[Session], T]) -> T:
    """
    Execute a database operation safely in a thread pool.
    
    The ENTIRE session lifecycle stays in one thread:
    - Session created in thread
    - fn() executed in thread  
    - Commit/rollback in thread
    - Session closed in thread
    
    Usage:
        async def get_user(user_id: int):
            def query(db: Session):
                return db.execute(select(User).where(User.id == user_id)).scalar_one_or_none()
            return await run_db(query)
    """
    def _execute():
        with SessionLocal() as session:
            try:
                result = fn(session)
                session.commit()
                return result
            except Exception:
                session.rollback()
                raise
    
    return await asyncio.to_thread(_execute)


async def check_database_connection() -> bool:
    """
    Verify Turso connection is working.
    Useful for health checks and startup validation.
    """
    try:
        def ping(db: Session):
            db.execute(text("SELECT 1"))
            return True
        return await run_db(ping)
    except Exception:
        return False
