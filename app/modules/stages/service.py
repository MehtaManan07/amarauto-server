"""
Stage service. Stages are a small config set (cutting/stitching/finishing/assembly),
so listing is unpaginated and ordered by sequence. name and sequence are unique.
"""

from typing import List
from sqlalchemy import select, or_
from sqlalchemy.orm import Session
from datetime import datetime

from app.core.db.engine import run_db
from app.core.exceptions import ConflictError, NotFoundError
from app.modules.production.service import invalidate_stages_cache
from app.modules.stages.models import Stage
from app.modules.stages.schemas import (
    StageCreateDto,
    StageUpdateDto,
    StageResponse,
)


def _to_response(row: Stage) -> StageResponse:
    return StageResponse(
        id=row.id,
        name=row.name,
        sequence=row.sequence,
        is_active=row.is_active,
        created_at=row.created_at,
        updated_at=row.updated_at,
        deleted_at=row.deleted_at,
    )


class StageService:
    @staticmethod
    async def create(dto: StageCreateDto) -> StageResponse:
        name = dto.name.strip().upper()  # stage names are stored uppercase

        def _create(db: Session) -> StageResponse:
            clash = db.execute(
                select(Stage).where(
                    Stage.deleted_at.is_(None),
                    or_(Stage.name == name, Stage.sequence == dto.sequence),
                )
            ).scalars().first()
            if clash:
                raise ConflictError("A stage with this name or sequence already exists")
            now = datetime.utcnow()
            row = Stage(
                name=name,
                sequence=dto.sequence,
                is_active=dto.is_active,
                created_at=now,
                updated_at=now,
            )
            db.add(row)
            db.flush()
            invalidate_stages_cache()
            return _to_response(row)

        return await run_db(_create)

    @staticmethod
    async def find_all(include_inactive: bool = True) -> List[StageResponse]:
        def _find_all(db: Session) -> List[StageResponse]:
            query = select(Stage).where(Stage.deleted_at.is_(None))
            if not include_inactive:
                query = query.where(Stage.is_active.is_(True))
            query = query.order_by(Stage.sequence)
            rows = db.execute(query).scalars().all()
            return [_to_response(r) for r in rows]

        return await run_db(_find_all)

    @staticmethod
    async def find_one(stage_id: int) -> StageResponse:
        def _find(db: Session) -> StageResponse:
            row = db.execute(
                select(Stage).where(Stage.id == stage_id, Stage.deleted_at.is_(None))
            ).scalar_one_or_none()
            if not row:
                raise NotFoundError("Stage", stage_id)
            return _to_response(row)

        return await run_db(_find)

    @staticmethod
    async def update(stage_id: int, dto: StageUpdateDto) -> StageResponse:
        def _update(db: Session) -> StageResponse:
            row = db.execute(
                select(Stage).where(Stage.id == stage_id, Stage.deleted_at.is_(None))
            ).scalar_one_or_none()
            if not row:
                raise NotFoundError("Stage", stage_id)
            data = dto.model_dump(exclude_unset=True)
            if "name" in data and data["name"] is not None:
                data["name"] = data["name"].strip().upper()
            # Guard the unique name/sequence against other rows.
            if "name" in data or "sequence" in data:
                new_name = data.get("name", row.name)
                new_seq = data.get("sequence", row.sequence)
                clash = db.execute(
                    select(Stage).where(
                        Stage.deleted_at.is_(None),
                        Stage.id != stage_id,
                        or_(Stage.name == new_name, Stage.sequence == new_seq),
                    )
                ).scalars().first()
                if clash:
                    raise ConflictError("A stage with this name or sequence already exists")
            for k, v in data.items():
                setattr(row, k, v)
            row.updated_at = datetime.utcnow()
            db.flush()
            invalidate_stages_cache()
            return _to_response(row)

        return await run_db(_update)

    @staticmethod
    async def remove(stage_id: int) -> None:
        def _remove(db: Session) -> None:
            row = db.execute(
                select(Stage).where(Stage.id == stage_id)
            ).scalar_one_or_none()
            if not row:
                raise NotFoundError("Stage", stage_id)
            row.deleted_at = datetime.utcnow()
            db.flush()
            invalidate_stages_cache()

        await run_db(_remove)
