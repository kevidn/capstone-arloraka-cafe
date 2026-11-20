import math
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db, require_management
from app.models.product import Product
from app.models.user import User
from app.schemas.product import (
    PaginatedProductResponse,
    ProductCreate,
    ProductResponse,
    ProductUpdate,
)

router = APIRouter(prefix="/products", tags=["products"])


@router.get("", response_model=PaginatedProductResponse)
async def list_products(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    page: int = Query(1, ge=1, description="Nomor halaman (mulai dari 1)"),
    page_size: int = Query(
        20,
        ge=1,
        le=100,
        description="Jumlah data per halaman (default 20, maks 100)",
    ),
    q: str | None = Query(
        None, description="Pencarian universal (nama atau kode produk)"
    ),
    active_only: bool = Query(True, description="Hanya tampilkan produk aktif"),
) -> PaginatedProductResponse:
    """Mengambil daftar produk dengan pagination dan search."""
    conditions = []
    if active_only:
        conditions.append(Product.is_active.is_(True))

    if q and q.strip():
        search_term = f"%{q.strip()}%"
        conditions.append(
            or_(
                Product.name.ilike(search_term),
                Product.product_code.ilike(search_term),
            )
        )

    # 1. Total count
    count_query = select(func.count(Product.id))
    if conditions:
        count_query = count_query.where(*conditions)
    total = (await db.execute(count_query)).scalar_one()

    # 2. Paginated data
    query = select(Product).order_by(Product.name.asc())
    if conditions:
        query = query.where(*conditions)

    query = query.offset((page - 1) * page_size).limit(page_size)
    items = list((await db.execute(query)).scalars().all())

    total_pages = math.ceil(total / page_size) if total > 0 else 0

    return PaginatedProductResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


@router.get("/{product_id}", response_model=ProductResponse)
async def get_product(
    product_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> Product:
    """Mengambil detail satu produk berdasarkan ID."""
    result = await db.execute(select(Product).where(Product.id == product_id))
    product = result.scalar_one_or_none()
    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Produk dengan ID {product_id} tidak ditemukan.",
        )
    return product


@router.post("", response_model=ProductResponse, status_code=status.HTTP_201_CREATED)
async def create_product(
    product_in: ProductCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_management)],
) -> Product:
    """Menambahkan produk baru (Khusus Manajemen)."""
    # Cek duplikasi nama produk
    existing = await db.execute(select(Product).where(Product.name == product_in.name))
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Produk dengan nama '{product_in.name}' sudah ada.",
        )

    product = Product(
        product_code=product_in.product_code,
        name=product_in.name,
        price=product_in.price,
        description=product_in.description,
        is_active=product_in.is_active,
    )
    db.add(product)
    await db.commit()
    await db.refresh(product)
    return product


@router.put("/{product_id}", response_model=ProductResponse)
async def update_product(
    product_id: int,
    product_in: ProductUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_management)],
) -> Product:
    """Memperbarui data produk (Khusus Manajemen)."""
    result = await db.execute(select(Product).where(Product.id == product_id))
    product = result.scalar_one_or_none()
    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Produk dengan ID {product_id} tidak ditemukan.",
        )

    update_data = product_in.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(product, field, value)

    await db.commit()
    await db.refresh(product)
    return product


@router.delete("/{product_id}", status_code=status.HTTP_200_OK)
async def delete_product(
    product_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_management)],
) -> dict[str, str]:
    """Menghapus atau menonaktifkan produk (Khusus Manajemen)."""
    result = await db.execute(select(Product).where(Product.id == product_id))
    product = result.scalar_one_or_none()
    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Produk dengan ID {product_id} tidak ditemukan.",
        )

    # Soft delete / toggle active
    product.is_active = False
    await db.commit()
    return {"message": f"Produk '{product.name}' berhasil dinonaktifkan."}
