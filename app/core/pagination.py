"""
Pagination utilities for reusable pagination across all services.

Provides helper functions to paginate SQLAlchemy queries and format responses.
Works with the immutable query builder pattern used throughout the application.

Uses COUNT(*) OVER() window function to get total + page data in a single query
(one DB round-trip instead of two).
"""

from typing import Tuple, List, Any
from sqlalchemy import func
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
    Uses COUNT(*) OVER() window function to get total + data in ONE query.

    IMPORTANT: Query should already have:
    - WHERE clauses (including soft-delete filters)
    - ORDER BY clause
    - Select a single entity (e.g. select(Product))

    Returns:
        Tuple of (paginated_items, total_count)
    """
    offset = (page - 1) * page_size
    count_col = func.count().over().label('_total_count')
    windowed = query.add_columns(count_col).offset(offset).limit(page_size)
    rows = db.execute(windowed).all()

    if not rows:
        return [], 0

    total = rows[0][-1]
    items = [row[0] for row in rows]
    return items, total


def paginate_multi(
    db: Session,
    query: Select,
    page: int = 1,
    page_size: int = 25,
) -> Tuple[List[Any], int]:
    """
    Paginate a multi-column select query (e.g. select(Entity, col1, col2)).
    Uses COUNT(*) OVER() window function to get total + data in ONE query.

    Returns:
        Tuple of (rows_without_count, total_count)
        Each row is a tuple of all original columns (without the _total_count).
    """
    offset = (page - 1) * page_size
    count_col = func.count().over().label('_total_count')
    windowed = query.add_columns(count_col).offset(offset).limit(page_size)
    rows = db.execute(windowed).all()

    if not rows:
        return [], 0

    total = rows[0][-1]
    items = [row[:-1] for row in rows]
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
