from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ProductBase(BaseModel):
    product_code: str | None = Field(
        None, description="Kode produk unik (misal PRD-001)"
    )
    name: str = Field(..., min_length=2, max_length=150)
    price: int = Field(..., gt=0, description="Harga produk per botol dalam Rupiah")
    description: str | None = None
    is_active: bool = True


class ProductCreate(ProductBase):
    pass


class ProductUpdate(BaseModel):
    product_code: str | None = None
    name: str | None = Field(None, min_length=2, max_length=150)
    price: int | None = Field(None, gt=0)
    description: str | None = None
    is_active: bool | None = None


class ProductResponse(ProductBase):
    id: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PaginatedProductResponse(BaseModel):
    items: list[ProductResponse]
    total: int = Field(..., description="Total produk sesuai filter/pencarian")
    page: int = Field(..., description="Halaman saat ini (mulai dari 1)")
    page_size: int = Field(..., description="Jumlah data per halaman")
    total_pages: int = Field(..., description="Total jumlah halaman")
