import asyncio
import logging
import sys
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.error_handler import global_exception_handler
from app.core.response_interceptor import (
    SuccessResponseInterceptor,
    CustomAPIRoute,
)
from app.core.config import config
from app.modules.users.router import router as users_router
from app.modules.raw_materials.router import router as raw_materials_router
from app.modules.products.router import router as products_router
from app.modules.bom.router import router as bom_router
from app.modules.dashboard.router import router as dashboard_router
from app.modules.inventory_logs.router import router as inventory_logs_router
from app.modules.parties.router import router as parties_router
from app.modules.stages.router import router as stages_router

# --- Phase 2 rewrite pending (new production-flow schema) ---
# job_rates -> operations, work_logs restructured, production -> batch flow.
# Their services still reference the old models; routers are disabled until rewritten.
# from app.modules.operations.router import router as operations_router
# from app.modules.work_logs.router import router as work_logs_router
# from app.modules.production.router import router as production_router

# Configure logging to output to console
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[logging.StreamHandler(sys.stdout)],
)

# Set logger for your app
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan manager.
    """
    from app.core.db.engine import check_database_connection

    # Cap the default asyncio executor used by run_db's asyncio.to_thread().
    # Matches the SQLAlchemy pool ceiling (pool_size + max_overflow = 30) so
    # we don't spawn more DB workers than we can give connections to.
    loop = asyncio.get_running_loop()
    loop.set_default_executor(ThreadPoolExecutor(max_workers=30, thread_name_prefix="db"))

    logger.info("Starting MyStock API...")
    logger.info(f"Connecting to Turso database: {config.turso_database_url}")

    # Verify database connection on startup
    if await check_database_connection():
        logger.info("Database connection verified successfully")
    else:
        logger.error("Failed to connect to database!")

    yield  # App runs here

    # Cleanup on shutdown
    logger.info("Shutting down MyStock API...")


app = FastAPI(
    title="Amar Autobiles API",
    description="Inventory management system with Turso (libSQL) backend",
    version="1.0.0",
    lifespan=lifespan,
)

# Override the default route class to support skip_interceptor decorator
app.router.route_class = CustomAPIRoute

# Add global exception handler
app.add_exception_handler(Exception, global_exception_handler)

# Middlewares
origins = [
    "http://localhost",
    "http://localhost:5173",
    "http://localhost:5174",
    "https://softx.surge.sh",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add Success Response Interceptor (must be added after CORS)
app.add_middleware(SuccessResponseInterceptor)

# Include routers with /api prefix
app.include_router(users_router, prefix="/api")
app.include_router(raw_materials_router, prefix="/api")
app.include_router(products_router, prefix="/api")
app.include_router(bom_router, prefix="/api")
app.include_router(dashboard_router, prefix="/api")
app.include_router(inventory_logs_router, prefix="/api")
app.include_router(parties_router, prefix="/api")
app.include_router(stages_router, prefix="/api")
# Phase 2 rewrite pending — see disabled imports above:
# app.include_router(operations_router, prefix="/api")
# app.include_router(work_logs_router, prefix="/api")
# app.include_router(production_router, prefix="/api")


@app.get("/demo")
async def demo() -> dict[str, str]:
    return {"message": "Hello World"}
