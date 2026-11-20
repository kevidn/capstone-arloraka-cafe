from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.report import ReportStatus
from app.schemas.product import ProductResponse
from app.schemas.user import UserResponse


class ReportItemBase(BaseModel):
    product_id: int
    quantity: int = Field(..., gt=0, description="Jumlah botol yang terjual")


class ReportItemCreate(ReportItemBase):
    pass


class ReportItemResponse(ReportItemBase):
    id: int
    unit_price: int
    subtotal: int
    product: ProductResponse | None = None

    model_config = ConfigDict(from_attributes=True)


class ProofResponse(BaseModel):
    id: int
    file_name: str
    file_path: str
    content_type: str
    file_size: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ReportCreate(BaseModel):
    report_date: datetime | None = None
    items: list[ReportItemCreate] = Field(..., min_length=1)


class ReportRevisionUpdate(BaseModel):
    items: list[ReportItemCreate] = Field(..., min_length=1)


class ReportVerifyRequest(BaseModel):
    status: ReportStatus = Field(
        ...,
        description="Keputusan verifikasi: 'approved', 'rejected', atau 'revision'",
    )
    revision_notes: str | None = Field(
        None,
        description="Wajib diisi jika status rejected atau revision",
    )


class ReportResponse(BaseModel):
    id: int
    freelancer_id: int
    freelancer: UserResponse | None = None
    report_date: datetime
    status: ReportStatus
    revision_notes: str | None = None
    total_bottles: int
    total_omzet: int
    commission_amount: int
    management_share: int
    is_flagged_anomaly: bool
    anomaly_reason: str | None = None
    items: list[ReportItemResponse] = []
    proofs: list[ProofResponse] = []
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PaginatedReportResponse(BaseModel):
    items: list[ReportResponse]
    total: int = Field(..., description="Total data sesuai filter")
    page: int = Field(..., description="Halaman saat ini (mulai dari 1)")
    page_size: int = Field(..., description="Jumlah data per halaman")
    total_pages: int = Field(..., description="Total jumlah halaman")
