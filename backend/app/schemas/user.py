from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.models.user import UserRole


class UserBase(BaseModel):
    name: str
    email: EmailStr
    freelancer_code: str | None = None
    role: UserRole = UserRole.FREELANCER


class UserCreate(UserBase):
    password: str


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class UserResponse(UserBase):
    id: int
    is_active: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PaginatedUserResponse(BaseModel):
    items: list[UserResponse]
    total: int = Field(..., description="Total pengguna sesuai filter/pencarian")
    page: int = Field(..., description="Halaman saat ini (mulai dari 1)")
    page_size: int = Field(..., description="Jumlah data per halaman")
    total_pages: int = Field(..., description="Total jumlah halaman")


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: UserRole
    user: UserResponse


class TokenData(BaseModel):
    sub: str | None = None
    role: str | None = None
