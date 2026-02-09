"""
Users service. All DB access via run_db(). find_all supports powerful search.
"""

from typing import List, Optional
from sqlalchemy import select, or_, cast, String
from sqlalchemy.orm import Session
from datetime import datetime

from app.core.db.engine import run_db
from app.core.exceptions import ConflictError, NotFoundError, UnauthorizedError
from app.core.utils import search_words
from app.modules.users.auth import AuthService
from app.modules.users.models import User, Role
from app.modules.users.schemas import (
    CreateUserDto,
    UpdateUserDto,
    UserResponse,
    RegisterRequest,
    RegisterResponse,
    LoginRequest,
    LoginResponse,
    TokenResponse,
)


def _user_to_response(user: User) -> UserResponse:
    return UserResponse(
        id=user.id,
        username=user.username,
        name=user.name,
        role=user.role,
        phone=user.phone,
        job=user.job,
        status=user.status,
        created_at=user.created_at,
        updated_at=user.updated_at,
        deleted_at=user.deleted_at,
    )


class UsersService:
    @staticmethod
    async def create(dto: CreateUserDto) -> RegisterResponse:
        """Create a new user and return user + token (for register flow)."""
        def _create(db: Session) -> RegisterResponse:
            existing = db.execute(select(User).where(User.username == dto.username))
            if existing.scalars().first():
                raise ConflictError("User already exists with this username")
            user = User(
                username=dto.username,
                password=AuthService.get_password_hash(dto.password),
                name=dto.name,
                role=dto.role,
                phone=dto.phone,
                job=dto.job,
            )
            db.add(user)
            db.flush()
            db.refresh(user)
            token_data = {"sub": user.username, "user_id": user.id, "role": user.role.value}
            access_token = AuthService.create_access_token(token_data)
            return RegisterResponse(
                user=_user_to_response(user),
                token=TokenResponse(access_token=access_token, token_type="bearer"),
            )
        return await run_db(_create)

    @staticmethod
    async def register(dto: RegisterRequest) -> RegisterResponse:
        """Register a new user (alias for create with RegisterRequest)."""
        create_dto = CreateUserDto(
            username=dto.username,
            password=dto.password,
            name=dto.name,
            role=dto.role,
            phone=dto.phone,
            job=dto.job,
        )
        return await UsersService.create(create_dto)

    @staticmethod
    async def login(dto: LoginRequest) -> LoginResponse:
        """Login: verify credentials and return user + token."""
        def _login(db: Session) -> LoginResponse:
            result = db.execute(
                select(User).where(
                    User.username == dto.username,
                    User.deleted_at.is_(None),
                )
            )
            user = result.scalar_one_or_none()
            if not user:
                raise UnauthorizedError("Invalid username or password")
            if not AuthService.verify_password(dto.password, user.password):
                raise UnauthorizedError("Invalid username or password")
            token_data = {"sub": user.username, "user_id": user.id, "role": user.role.value}
            access_token = AuthService.create_access_token(token_data)
            return LoginResponse(
                user=_user_to_response(user),
                token=TokenResponse(access_token=access_token, token_type="bearer"),
            )
        return await run_db(_login)

    @staticmethod
    async def find_all(search: Optional[str] = None) -> List[UserResponse]:
        """
        List non-deleted users. Optional search: split into words; each word must match
        at least one of username, name, phone, job, role, status (powerful multi-field search).
        """
        words = search_words(search)

        def _find_all(db: Session) -> List[UserResponse]:
            query = select(User).where(User.deleted_at.is_(None))
            for word in words:
                pattern = f"%{word}%"
                query = query.where(
                    or_(
                        User.username.ilike(pattern),
                        User.name.ilike(pattern),
                        User.phone.ilike(pattern),
                        User.job.ilike(pattern),
                        cast(User.role, String).ilike(pattern),
                        cast(User.status, String).ilike(pattern),
                    )
                )
            query = query.order_by(User.created_at.desc())
            result = db.execute(query)
            users = result.scalars().all()
            return [_user_to_response(u) for u in users]
        return await run_db(_find_all)

    @staticmethod
    async def find_by_role(roles: List[Role]) -> List[UserResponse]:
        """List users filtered by role(s)."""
        def _find(db: Session) -> List[UserResponse]:
            result = db.execute(
                select(User).where(
                    User.role.in_(roles),
                    User.deleted_at.is_(None),
                ).order_by(User.created_at.desc())
            )
            users = result.scalars().all()
            return [_user_to_response(u) for u in users]
        return await run_db(_find)

    @staticmethod
    async def find_one(user_id: int) -> UserResponse:
        """Get user by id (non-deleted)."""
        def _find(db: Session) -> UserResponse:
            result = db.execute(
                select(User).where(User.id == user_id, User.deleted_at.is_(None))
            )
            user = result.scalar_one_or_none()
            if not user:
                raise NotFoundError("User", user_id)
            return _user_to_response(user)
        return await run_db(_find)

    @staticmethod
    async def find_me(user_id: int) -> UserResponse:
        """Get current user by id (for /me; ignores deleted_at for self)."""
        def _find(db: Session) -> UserResponse:
            result = db.execute(select(User).where(User.id == user_id))
            user = result.scalar_one_or_none()
            if not user:
                raise NotFoundError("User", user_id)
            return _user_to_response(user)
        return await run_db(_find)

    @staticmethod
    async def update(user_id: int, dto: UpdateUserDto) -> UserResponse:
        """Update user; returns updated user."""
        def _update(db: Session) -> UserResponse:
            result = db.execute(select(User).where(User.id == user_id))
            user = result.scalar_one_or_none()
            if not user:
                raise NotFoundError("User", user_id)
            data = dto.model_dump(exclude_unset=True)
            for k, v in data.items():
                setattr(user, k, v)
            db.flush()
            db.refresh(user)
            return _user_to_response(user)
        return await run_db(_update)

    @staticmethod
    async def remove(user_id: int) -> None:
        """Soft delete user."""
        def _remove(db: Session) -> None:
            result = db.execute(select(User).where(User.id == user_id))
            user = result.scalar_one_or_none()
            if not user:
                raise NotFoundError("User", user_id)
            user.deleted_at = datetime.utcnow()
            db.flush()
        await run_db(_remove)
