# Only export base classes to prevent circular import issues
# Models should be imported directly from their respective modules

from app.core.db.base import Base, BaseModel

__all__ = [
    "Base",
    "BaseModel",
]
