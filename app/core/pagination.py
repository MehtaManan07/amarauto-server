"""
Pagination utilities for reusable pagination across all services.

Provides helper functions to paginate SQLAlchemy queries and format responses.
Works with the immutable query builder pattern used throughout the application.
"""

from typing import Tuple, List, Any
from sqlalchemy import select, func
from sqlalchemy.orm import Session
from sqlalchemy.sql.selectable import Select


def paginate_query(
    db: Session,
    query: Select,
    page: int = 1,
    page_size: int = 25,
) -> Tuple[List[Any], int]:
    """
    Apply offset-based pagination to a SQLAlchemy query.

    IMPORTANT: Query should already have:
    - WHERE clauses (including soft-delete filters)
    - Eager loading (selectinload) to prevent N+1 queries
    - ORDER BY clause

    This function:
    1. Counts total matching records (before pagination)
    2. Applies OFFSET and LIMIT
    3. Executes and returns (items, total_count)

    Args:
        db: SQLAlchemy session
        query: Base query with filters and ordering already applied
        page: Page number (1-indexed, default 1)
        page_size: Items per page (default 25)

    Returns:
        Tuple of (paginated_items, total_count)
    """
    # Count total records BEFORE pagination
    # Using subquery to preserve all WHERE clauses and joins
    count_query = select(func.count()).select_from(query.subquery())
    total = db.execute(count_query).scalar()

    # Apply offset and limit
    offset = (page - 1) * page_size
    paginated_query = query.offset(offset).limit(page_size)

    # Execute paginated query
    result = db.execute(paginated_query)
    items = result.scalars().all()

    return items, total


def build_paginated_response(
    items: List[dict],
    total: int,
    page: int,
    page_size: int,
) -> dict:
    """
    Build a standardized paginated response dictionary.

    Args:
        items: List of items for current page
        total: Total count of all items matching filters
        page: Current page number (1-indexed)
        page_size: Items per page

    Returns:
        Dict with keys: items, total, page, page_size, total_pages, has_more
    """
    total_pages = (total + page_size - 1) // page_size if total > 0 else 0
    has_more = page < total_pages

    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": total_pages,
        "has_more": has_more,
    }
