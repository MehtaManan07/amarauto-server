"""
Simple error handling for the application.
"""

import logging
from fastapi import Request, HTTPException
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from sqlalchemy.exc import SQLAlchemyError

from .exceptions import (
    ValidationError,
    NotFoundError,
    ConflictError,
    DatabaseError,
    ExternalServiceError,
)

logger = logging.getLogger(__name__)


async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Simple global exception handler for FastAPI."""

    if isinstance(
        exc,
        (
            ValidationError,
            NotFoundError,
            ConflictError,
            DatabaseError,
            ExternalServiceError,
        ),
    ):
        logger.error(f"Application error: {exc.detail}")
        return JSONResponse(
            status_code=exc.status_code, content={"error": {"message": exc.detail}}
        )
    elif isinstance(exc, HTTPException):
        logger.warning(f"HTTP exception: {exc.detail}")
        return JSONResponse(
            status_code=exc.status_code, content={"error": {"message": str(exc.detail)}}
        )
    elif isinstance(exc, RequestValidationError):
        logger.warning(f"Validation error: {exc.errors()}")
        return JSONResponse(
            status_code=422,
            content={
                "error": {"message": "Validation failed", "details": exc.errors()}
            },
        )
    elif isinstance(exc, SQLAlchemyError):
        logger.error(f"Database error: {str(exc)}")
        return JSONResponse(
            status_code=500, content={"error": {"message": "Database operation failed"}}
        )
    else:
        logger.error(f"Unexpected error: {str(exc)}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={"error": {"message": "An unexpected error occurred"}},
        )
