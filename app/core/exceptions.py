"""
Simple exception classes for the application.
"""

from fastapi import HTTPException, status


class ValidationError(HTTPException):
    """Raised when input validation fails."""

    def __init__(self, message: str):
        super().__init__(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=message
        )


class NotFoundError(HTTPException):
    """Raised when a requested resource is not found."""

    def __init__(self, resource_type: str, resource_id):
        super().__init__(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"{resource_type} not found"
        )


class ConflictError(HTTPException):
    """Raised when there's a conflict with existing data."""

    def __init__(self, message: str):
        super().__init__(status_code=status.HTTP_409_CONFLICT, detail=message)


class DatabaseError(HTTPException):
    """Raised when database operations fail."""

    def __init__(self, message: str = "Database operation failed"):
        super().__init__(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=message
        )


class ExternalServiceError(HTTPException):
    """Raised when external service calls fail."""

    def __init__(self, service_name: str, message: str):
        super().__init__(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"{service_name} service error: {message}",
        )

class UnauthorizedError(HTTPException):
    """Raised when a user is not authorized to access a resource."""

    def __init__(self, message: str):
        super().__init__(status_code=status.HTTP_401_UNAUTHORIZED, detail=message)