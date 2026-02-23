from pydantic import BaseModel, EmailStr, Field
from datetime import datetime
from uuid import UUID


class UserRegister(BaseModel):
    """Schema for user registration"""

    email: EmailStr
    password: str = Field(
        ...,
        min_length=8,
        max_length=100,
        description="Password must be at least 8 characters",
    )


class UserLogin(BaseModel):
    """Schema for user login (OAuth2 compatible)"""

    username: EmailStr  # OAuth2 spec uses 'username' field
    password: str


class Token(BaseModel):
    """Schema for JWT token response"""

    access_token: str
    token_type: str = "bearer"


class UserResponse(BaseModel):
    """Schema for user information response"""

    id: UUID
    email: str
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True
