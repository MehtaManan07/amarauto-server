import logging
import sys
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
# from app.modules.products import router as products_router
# from app.modules.containers import router as containers_router
# from app.modules.container_products import router as container_products_router
# from app.modules.contacts import router as contacts_router
# from app.modules.transactions import router as transactions_router
# from app.modules.inventory_logs import router as inventory_logs_router
# from app.modules.payments import router as payments_router
# from app.modules.settings import router as settings_router
# from app.modules.vendor_product_skus import router as vendor_skus_router

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
# app.include_router(products_router, prefix="/api")
# app.include_router(containers_router, prefix="/api")
# app.include_router(container_products_router, prefix="/api")
# app.include_router(contacts_router, prefix="/api")
# app.include_router(transactions_router, prefix="/api")
# app.include_router(inventory_logs_router, prefix="/api")
# app.include_router(payments_router, prefix="/api")
# app.include_router(settings_router, prefix="/api")
# app.include_router(vendor_skus_router, prefix="/api")


@app.get("/demo")
async def demo() -> dict[str, str]:
    return {"message": "Hello World"}
