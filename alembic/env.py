"""
Alembic environment configuration for Turso (libSQL).

Uses synchronous engine for Turso via sqlalchemy-libsql.
"""

import os
from logging.config import fileConfig
from sqlalchemy import create_engine
from sqlalchemy.engine import Connection
from alembic import context
from dotenv import load_dotenv

# Import your models here for autogenerate support
from app.core.db.base import Base
from app.modules.users.models import User
from app.modules.raw_materials.models import RawMaterial
from app.modules.products.models import Product

# Load .env
load_dotenv()

config = context.config

# -------------------------------
# TURSO DATABASE CONFIGURATION
# -------------------------------
TURSO_DATABASE_URL = os.getenv("TURSO_DATABASE_URL")
TURSO_AUTH_TOKEN = os.getenv("TURSO_AUTH_TOKEN")

if not TURSO_DATABASE_URL or not TURSO_AUTH_TOKEN:
    raise ValueError("TURSO_DATABASE_URL and TURSO_AUTH_TOKEN must be set in .env")

# Build SQLAlchemy URL for libSQL
db_url = TURSO_DATABASE_URL.replace("libsql://", "sqlite+libsql://") + "?secure=true"
config.set_main_option("sqlalchemy.url", db_url)

# Logging
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Target metadata for autogenerate
target_metadata = Base.metadata


# -------------------------------
# RUN MIGRATIONS OFFLINE
# -------------------------------
def run_migrations_offline() -> None:
    """Generate SQL without connecting to the database."""
    context.configure(
        url=db_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        compare_server_default=True,
        render_as_batch=True,  # Required for SQLite-based databases
    )
    with context.begin_transaction():
        context.run_migrations()


# -------------------------------
# RUN MIGRATIONS ONLINE
# -------------------------------
def do_run_migrations(connection: Connection) -> None:
    """Run migrations on the given connection."""
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
        compare_server_default=True,
        render_as_batch=True,  # Required for SQLite-based databases
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    connectable = create_engine(
        db_url,
        connect_args={"auth_token": TURSO_AUTH_TOKEN},
        pool_pre_ping=True,
    )

    with connectable.connect() as connection:
        do_run_migrations(connection)


# -------------------------------
# EXECUTION
# -------------------------------
if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
