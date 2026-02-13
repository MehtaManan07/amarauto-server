"""
Users router. Auth and role-based protection. List supports powerful search.
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, Query

from app.core.response_interceptor import skip_interceptor
from .service import UsersService
from .schemas import (
    CreateUserDto,
    UpdateUserDto,
    UserResponse,
    LoginRequest,
    LoginResponse,
)
from .models import Role
from .auth import get_current_user, TokenData, require_admin, require_admin_or_supervisor, require_any_role

router = APIRouter(prefix="/users", tags=["users"])


# --- Auth ---

@router.post("/login", response_model=LoginResponse)
async def login(dto: LoginRequest):
    """Login with username/password. Returns user + JWT."""
    return await UsersService.login(dto)


# --- Users (protected) ---

@router.post("", response_model=UserResponse)
async def create_user(
    dto: CreateUserDto,
    current_user: TokenData = Depends(require_admin),
):
    """Create a new user (Admin only). No self-registration."""
    return await UsersService.create_by_admin(dto)


@router.get("", response_model=List[UserResponse])
async def list_users(
    search: Optional[str] = Query(None, description="Search across username, name, phone, job, role, status (words AND'd)"),
    current_user: TokenData = Depends(require_admin_or_supervisor),
):
    """List all users (Admin or Supervisor). Optional search: split into words, each word matches any field."""
    return await UsersService.find_all(search=search)


@router.get("/role", response_model=List[UserResponse])
async def list_users_by_role(
    role: List[Role] = Query(..., description="Filter by role(s), e.g. ?role=Admin&role=Worker"),
    current_user: TokenData = Depends(require_admin_or_supervisor),
):
    """List users filtered by role(s)."""
    return await UsersService.find_by_role(role)


@router.get("/me", response_model=UserResponse)
async def get_me(current_user: TokenData = Depends(get_current_user)):
    """Current user profile from JWT."""
    return await UsersService.find_me(current_user.user_id)


@router.get("/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: int,
    current_user: TokenData = Depends(require_any_role),
):
    """Get user by id."""
    return await UsersService.find_one(user_id)


@router.patch("/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: int,
    dto: UpdateUserDto,
    current_user: TokenData = Depends(require_admin),
):
    """Update user (Admin only)."""
    return await UsersService.update(user_id, dto)


@router.delete("/{user_id}")
@skip_interceptor
async def delete_user(
    user_id: int,
    current_user: TokenData = Depends(require_admin),
):
    """Soft delete user (Admin only)."""
    await UsersService.remove(user_id)
    return {"message": "User deleted successfully"}
