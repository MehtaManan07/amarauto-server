"""
Turso (libSQL) Database Engine Configuration for FastAPI.

Uses synchronous SQLAlchemy with asyncio.to_thread() for async compatibility.
Thread-safe: entire session lifecycle stays in a single thread.
"""

from typing import TypeVar, Callable
import asyncio

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import config as settings

T = TypeVar('T')

# Build Turso URL: sqlite+libsql://host?secure=true
# TURSO_DATABASE_URL contains "libsql://host", so we replace the scheme
turso_url = settings.turso_database_url.replace("libsql://", "sqlite+libsql://") + "?secure=true"

# Create sync engine for Turso
engine = create_engine(
    turso_url,
    connect_args={"auth_token": settings.turso_auth_token},
    echo=False,
    # Connection validation and pooling for Turso/libSQL HTTP streams
    pool_pre_ping=True,  # Test connections before using them
    pool_recycle=3600,   # Recycle connections after 1 hour
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
