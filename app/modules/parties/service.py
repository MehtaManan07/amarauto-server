"""
Parties service. CRUD with search (name, email, state, contact_person, mobile, gstin)
and filters (state, party_type). Field options for dropdowns.
"""

from typing import Dict, List, Optional
from sqlalchemy import select, or_, union_all, literal
from sqlalchemy.orm import Session
from datetime import datetime

from app.core.db.engine import run_db
from app.core.exceptions import ConflictError, NotFoundError
from app.core.pagination import paginate_query, build_paginated_response
from app.core.utils import search_words, normalize_text_fields
from app.modules.parties.models import Party
from app.modules.parties.schemas import (
    PartyCreateDto,
    PartyUpdateDto,
    PartyResponse,
    PartyPaginatedResponse,
    PartyFieldOptionsResponse,
)

PARTY_TEXT_FIELDS = (
    "name",
    "email",
    "state",
    "party_type",
    "address_line_1",
    "address_line_2",
    "address_line_3",
    "address_line_4",
    "address_line_5",
    "pin_code",
    "phone",
    "fax",
    "contact_person",
    "mobile",
    "gstin",
)


def _to_response(row: Party) -> PartyResponse:
    return PartyResponse(
        id=row.id,
        name=row.name,
        email=row.email,
        state=row.state,
        party_type=row.party_type,
        address_line_1=row.address_line_1,
        address_line_2=row.address_line_2,
        address_line_3=row.address_line_3,
        address_line_4=row.address_line_4,
        address_line_5=row.address_line_5,
        pin_code=row.pin_code,
        phone=row.phone,
        fax=row.fax,
        contact_person=row.contact_person,
        mobile=row.mobile,
        gstin=row.gstin,
        created_at=row.created_at,
        updated_at=row.updated_at,
        deleted_at=row.deleted_at,
    )


ALLOWED_FIELD_OPTIONS_FIELDS = ("state", "party_type")


class PartyService:
    @staticmethod
    async def get_field_options(
        fields: Optional[List[str]] = None,
    ) -> Dict[str, List[str]]:
        """
        Return distinct non-null values for state, party_type from non-deleted parties.
        Used by frontend for dropdowns; users can still enter new values.
        """
        requested = (
            [f for f in fields if f in ALLOWED_FIELD_OPTIONS_FIELDS]
            if fields
            else list(ALLOWED_FIELD_OPTIONS_FIELDS)
        )
        if not requested:
            return {}

        def _get_options(db: Session) -> Dict[str, List[str]]:
            subqueries = [
                select(literal(field).label("field"), getattr(Party, field).label("value"))
                .where(Party.deleted_at.is_(None), getattr(Party, field).isnot(None))
                .distinct()
                for field in requested
            ]
            rows = db.execute(union_all(*subqueries)).all()
            out: Dict[str, List[str]] = {f: [] for f in requested}
            for field_name, value in rows:
                out[field_name].append(value)
            for field_name in out:
                out[field_name].sort()
            return out

        return await run_db(_get_options)

    @staticmethod
    async def create(dto: PartyCreateDto) -> PartyResponse:
        def _create(db: Session) -> PartyResponse:
            existing = db.execute(
                select(Party).where(
                    Party.name == dto.name, Party.deleted_at.is_(None)
                )
            )
            if existing.scalars().first():
                raise ConflictError("Party already exists with this name")
            data = normalize_text_fields(
                dto.model_dump(), PARTY_TEXT_FIELDS
            )
            row = Party(**data)
            db.add(row)
            db.flush()
            db.refresh(row)
            return _to_response(row)
        return await run_db(_create)

    @staticmethod
    async def find_all_paginated(
        page: int = 1,
        page_size: int = 25,
        search: Optional[str] = None,
        state: Optional[str] = None,
        party_type: Optional[str] = None,
    ) -> dict:
        """
        Find all parties with pagination. Search across name, email, state,
        contact_person, mobile, gstin (words AND'd). Filters: state, party_type.
        """
        words = search_words(search)

        def _find_all_paginated(db: Session) -> dict:
            query = select(Party).where(Party.deleted_at.is_(None))
            if state:
                query = query.where(Party.state == state)
            if party_type:
                query = query.where(Party.party_type == party_type)
            for word in words:
                pattern = f"%{word}%"
                query = query.where(
                    or_(
                        Party.name.ilike(pattern),
                        Party.email.ilike(pattern),
                        Party.state.ilike(pattern),
                        Party.contact_person.ilike(pattern),
                        Party.mobile.ilike(pattern),
                        Party.gstin.ilike(pattern),
                    )
                )
            query = query.order_by(Party.name)
            rows, total = paginate_query(db, query, page, page_size)
            items = [_to_response(r) for r in rows]
            return build_paginated_response(items, total or 0, page, page_size)

        return await run_db(_find_all_paginated)

    @staticmethod
    async def find_one(party_id: int) -> PartyResponse:
        def _find(db: Session) -> PartyResponse:
            result = db.execute(
                select(Party).where(
                    Party.id == party_id,
                    Party.deleted_at.is_(None),
                )
            )
            row = result.scalar_one_or_none()
            if not row:
                raise NotFoundError("Party", party_id)
            return _to_response(row)
        return await run_db(_find)

    @staticmethod
    async def update(party_id: int, dto: PartyUpdateDto) -> PartyResponse:
        def _update(db: Session) -> PartyResponse:
            result = db.execute(
                select(Party).where(
                    Party.id == party_id,
                    Party.deleted_at.is_(None),
                )
            )
            row = result.scalar_one_or_none()
            if not row:
                raise NotFoundError("Party", party_id)
            data = dto.model_dump(exclude_unset=True)
            data = normalize_text_fields(data, PARTY_TEXT_FIELDS)
            for k, v in data.items():
                setattr(row, k, v)
            db.flush()
            db.refresh(row)
            return _to_response(row)
        return await run_db(_update)

    @staticmethod
    async def remove(party_id: int) -> None:
        def _remove(db: Session) -> None:
            result = db.execute(select(Party).where(Party.id == party_id))
            row = result.scalar_one_or_none()
            if not row:
                raise NotFoundError("Party", party_id)
            row.deleted_at = datetime.utcnow()
            db.flush()
        await run_db(_remove)
