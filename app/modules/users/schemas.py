"""
User and WorkLog DTOs (Data Transfer Objects).
"""

from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime

from .models import Role, Status


# --- User ---

class CreateUserDto(BaseModel):
    """DTO for creating a user (register or admin create)."""
    username: str = Field(..., min_length=1, max_length=255)
    password: str = Field(..., min_length=1)
    name: str = Field(..., min_length=1, max_length=255)
    role: Role = Field(default=Role.WORKER)
    phone: Optional[str] = Field(None, max_length=20)
    job: Optional[str] = Field(None, max_length=255)

    class Config:
        from_attributes = True


class UpdateUserDto(BaseModel):
    """DTO for updating user information."""
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    role: Optional[Role] = None
    phone: Optional[str] = Field(None, max_length=20)
    job: Optional[str] = Field(None, max_length=255)
    status: Optional[Status] = None
    password: Optional[str] = Field(None, min_length=1)

    class Config:
        from_attributes = True


class UserResponse(BaseModel):
    """Response model for User (no password)."""
    id: int
    username: str
    name: str
    role: Role
    phone: Optional[str] = None
    job: Optional[str] = None
    status: Status
    created_at: datetime
    updated_at: datetime
    deleted_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class LoginRequest(BaseModel):
    username: str
    password: str

    class Config:
        from_attributes = True


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"

    class Config:
        from_attributes = True


class RegisterRequest(BaseModel):
    username: str = Field(..., min_length=1, max_length=255)
    password: str = Field(..., min_length=1)
    name: str = Field(..., min_length=1, max_length=255)
    role: Role = Field(default=Role.WORKER)
    phone: Optional[str] = Field(None, max_length=20)
    job: Optional[str] = Field(None, max_length=255)

    class Config:
        from_attributes = True


class RegisterResponse(BaseModel):
    user: UserResponse
    token: TokenResponse

    class Config:
        from_attributes = True


class LoginResponse(BaseModel):
    user: UserResponse
    token: TokenResponse

    class Config:
        from_attributes = True
