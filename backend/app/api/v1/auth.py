import math
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db, require_management
from app.core.security import create_access_token, get_password_hash, verify_password
from app.models.user import User, UserRole
from app.schemas.user import (
    PaginatedUserResponse,
    Token,
    UserCreate,
    UserLogin,
    UserResponse,
)

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post(
    "/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED
)
async def register(
    user_in: UserCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> User:
    """Mendaftarkan akun baru (freelancer atau manajemen)."""
    # Cek apakah email sudah terdaftar
    existing = await db.execute(select(User).where(User.email == user_in.email))
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email sudah terdaftar di sistem.",
        )

    user = User(
        name=user_in.name,
        email=user_in.email,
        freelancer_code=user_in.freelancer_code,
        hashed_password=get_password_hash(user_in.password),
        role=user_in.role,
        is_active=True,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


@router.post("/login", response_model=Token)
async def login(
    user_in: UserLogin,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Token:
    """Login menggunakan email dan password untuk mendapatkan token JWT."""
    result = await db.execute(select(User).where(User.email == user_in.email))
    user = result.scalar_one_or_none()

    if not user or not verify_password(user_in.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email atau password salah.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Akun dinonaktifkan.",
        )

    access_token = create_access_token(
        subject=user.id,
        role=user.role.value,
        extra_claims={"email": user.email, "name": user.name},
    )

    return Token(
        access_token=access_token,
        token_type="bearer",
        role=user.role,
        user=UserResponse.model_validate(user),
    )


@router.get("/me", response_model=UserResponse)
async def get_me(
    current_user: Annotated[User, Depends(get_current_user)],
) -> User:
    """Mendapatkan profil pengguna yang sedang login."""
    return current_user


@router.get("/users", response_model=PaginatedUserResponse)
async def list_users(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_management)],
    page: int = Query(1, ge=1, description="Nomor halaman (mulai dari 1)"),
    page_size: int = Query(
        20,
        ge=1,
        le=100,
        description="Jumlah data per halaman (default 20, maks 100)",
    ),
    q: str | None = Query(
        None,
        description="Pencarian universal (nama, email, atau kode freelancer)",
    ),
    role: UserRole | None = Query(None, description="Filter peran pengguna"),
) -> PaginatedUserResponse:
    """Mengambil daftar seluruh pengguna/freelancer dengan pagination dan pencarian (Khusus Manajemen)."""
    conditions = []
    if role:
        conditions.append(User.role == role)

    if q and q.strip():
        search_term = f"%{q.strip()}%"
        conditions.append(
            or_(
                User.name.ilike(search_term),
                User.email.ilike(search_term),
                User.freelancer_code.ilike(search_term),
            )
        )

    count_query = select(func.count(User.id))
    if conditions:
        count_query = count_query.where(*conditions)
    total = (await db.execute(count_query)).scalar_one()

    query = select(User).order_by(User.id.asc())
    if conditions:
        query = query.where(*conditions)

    query = query.offset((page - 1) * page_size).limit(page_size)
    items = list((await db.execute(query)).scalars().all())

    total_pages = math.ceil(total / page_size) if total > 0 else 0

    return PaginatedUserResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )
