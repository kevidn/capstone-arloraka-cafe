import math
import os
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated

from fastapi import (
    APIRouter,
    Depends,
    File,
    HTTPException,
    Query,
    UploadFile,
    status,
)
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import (
    get_current_user,
    get_db,
    require_freelancer,
    require_management,
)
from app.core.calculation import calculate_commission, calculate_management_share
from app.models.product import Product
from app.models.proof import Proof
from app.models.report import Report, ReportItem, ReportStatus
from app.models.user import User, UserRole
from app.schemas.report import (
    PaginatedReportResponse,
    ProofResponse,
    ReportCreate,
    ReportItemCreate,
    ReportResponse,
    ReportRevisionUpdate,
    ReportVerifyRequest,
)

router = APIRouter(prefix="/reports", tags=["reports"])

UPLOAD_DIR = Path("uploads/proofs")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
ALLOWED_MIME_TYPES = {
    "image/jpeg",
    "image/png",
    "image/webp",
    "application/pdf",
}


async def _calculate_report_totals(
    items_in: list[ReportItemCreate],
    db: AsyncSession,
) -> tuple[int, int, int, int, list[dict]]:
    """Helper untuk validasi produk dan hitung total botol, omzet, komisi 10% round up."""
    total_bottles = 0
    total_omzet = 0
    computed_items = []

    for item in items_in:
        prod_res = await db.execute(
            select(Product).where(Product.id == item.product_id)
        )
        product = prod_res.scalar_one_or_none()
        if not product:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Produk dengan ID {item.product_id} tidak valid.",
            )
        if not product.is_active:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Produk '{product.name}' sedang tidak aktif.",
            )

        subtotal = product.price * item.quantity
        total_bottles += item.quantity
        total_omzet += subtotal

        computed_items.append(
            {
                "product_id": product.id,
                "quantity": item.quantity,
                "unit_price": product.price,
                "subtotal": subtotal,
            }
        )

    commission = calculate_commission(total_omzet)
    management_share = calculate_management_share(total_omzet, commission)

    return total_bottles, total_omzet, commission, management_share, computed_items


@router.post("", response_model=ReportResponse, status_code=status.HTTP_201_CREATED)
async def create_report(
    report_in: ReportCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_freelancer)],
) -> Report:
    """Freelancer mengirim laporan penjualan baru."""
    (
        total_bottles,
        total_omzet,
        commission,
        management_share,
        computed_items,
    ) = await _calculate_report_totals(report_in.items, db)

    report_date = report_in.report_date or datetime.now(UTC)

    report = Report(
        freelancer_id=current_user.id,
        report_date=report_date,
        status=ReportStatus.PENDING,
        total_bottles=total_bottles,
        total_omzet=total_omzet,
        commission_amount=commission,
        management_share=management_share,
    )
    db.add(report)
    await db.flush()  # dapatkan report.id

    for item_data in computed_items:
        item_obj = ReportItem(
            report_id=report.id,
            product_id=item_data["product_id"],
            quantity=item_data["quantity"],
            unit_price=item_data["unit_price"],
            subtotal=item_data["subtotal"],
        )
        db.add(item_obj)

    await db.commit()

    # Re-fetch dengan relasi lengkap
    result = await db.execute(
        select(Report)
        .options(
            selectinload(Report.items).joinedload(ReportItem.product),
            selectinload(Report.proofs),
            selectinload(Report.freelancer),
        )
        .where(Report.id == report.id)
    )
    return result.scalar_one()


@router.post(
    "/{report_id}/proofs",
    response_model=ProofResponse,
    status_code=status.HTTP_201_CREATED,
)
async def upload_report_proof(
    report_id: int,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Proof:
    """Mengunggah file bukti penjualan (foto nota / transfer / botol)."""
    result = await db.execute(select(Report).where(Report.id == report_id))
    report = result.scalar_one_or_none()
    if not report:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Laporan dengan ID {report_id} tidak ditemukan.",
        )

    # Hanya pemilik laporan atau manajemen yang boleh upload
    if (
        current_user.role != UserRole.MANAGEMENT
        and report.freelancer_id != current_user.id
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Anda tidak memiliki izin mengunggah bukti pada laporan ini.",
        )

    # Validasi content type
    content_type = file.content_type or "application/octet-stream"
    if content_type not in ALLOWED_MIME_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Tipe file tidak didukung. Harap unggah format JPG, PNG, WEBP, atau PDF.",
        )

    # Simpan file secara unik
    file_ext = os.path.splitext(file.filename or "")[1] or ".bin"
    unique_filename = f"{report_id}_{uuid.uuid4().hex[:10]}{file_ext}"
    saved_path = UPLOAD_DIR / unique_filename

    content = await file.read()
    with open(saved_path, "wb") as f:
        f.write(content)

    proof = Proof(
        report_id=report.id,
        file_name=file.filename or unique_filename,
        file_path=str(saved_path).replace("\\", "/"),
        content_type=content_type,
        file_size=len(content),
    )
    db.add(proof)
    await db.commit()
    await db.refresh(proof)
    return proof


@router.get("", response_model=PaginatedReportResponse)
async def list_reports(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    page: int = Query(1, ge=1, description="Nomor halaman (mulai dari 1)"),
    page_size: int = Query(
        20,
        ge=1,
        le=100,
        description="Jumlah data per halaman (default 20, maks 100)",
    ),
    status_filter: ReportStatus | None = Query(
        None, alias="status", description="Filter berdasarkan status laporan"
    ),
    freelancer_id: int | None = Query(
        None, description="Filter ID freelancer (Khusus Manajemen)"
    ),
    q: str | None = Query(
        None,
        description="Pencarian universal (ID transaksi, lokasi, metode bayar, catatan, nama freelancer)",
    ),
) -> PaginatedReportResponse:
    """Mengambil daftar laporan dengan pagination dan pencarian universal.

    - Manajemen: melihat seluruh laporan (bisa difilter per status / freelancer).
    - Freelancer: HANYA melihat laporan miliknya sendiri.
    """
    base_conditions = []

    if current_user.role == UserRole.FREELANCER:
        base_conditions.append(Report.freelancer_id == current_user.id)
    else:
        if freelancer_id is not None:
            base_conditions.append(Report.freelancer_id == freelancer_id)

    if status_filter:
        base_conditions.append(Report.status == status_filter)

    if q and q.strip():
        search_term = f"%{q.strip()}%"
        base_conditions.append(
            or_(
                Report.source_transaction_id.ilike(search_term),
                Report.sale_location.ilike(search_term),
                Report.payment_method.ilike(search_term),
                Report.notes.ilike(search_term),
                Report.freelancer.has(User.name.ilike(search_term)),
            )
        )

    # 1. Hitung total data sesuai filter
    count_query = select(func.count(Report.id))
    if base_conditions:
        count_query = count_query.where(*base_conditions)
    total = (await db.execute(count_query)).scalar_one()

    # 2. Query data dengan offset & limit
    query = (
        select(Report)
        .options(
            selectinload(Report.items).joinedload(ReportItem.product),
            selectinload(Report.proofs),
            selectinload(Report.freelancer),
        )
        .order_by(Report.report_date.desc(), Report.id.desc())
    )
    if base_conditions:
        query = query.where(*base_conditions)

    query = query.offset((page - 1) * page_size).limit(page_size)
    items = list((await db.execute(query)).scalars().all())

    total_pages = math.ceil(total / page_size) if total > 0 else 0

    return PaginatedReportResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


@router.get("/{report_id}", response_model=ReportResponse)
async def get_report_detail(
    report_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> Report:
    """Mengambil detail satu laporan beserta rincian item dan buktinya."""
    result = await db.execute(
        select(Report)
        .options(
            selectinload(Report.items).joinedload(ReportItem.product),
            selectinload(Report.proofs),
            selectinload(Report.freelancer),
        )
        .where(Report.id == report_id)
    )
    report = result.scalar_one_or_none()
    if not report:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Laporan dengan ID {report_id} tidak ditemukan.",
        )

    # Validasi akses hak milik
    if (
        current_user.role == UserRole.FREELANCER
        and report.freelancer_id != current_user.id
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Akses ditolak. Anda tidak berhak melihat laporan freelancer lain.",
        )

    return report


@router.patch("/{report_id}/verify", response_model=ReportResponse)
async def verify_report(
    report_id: int,
    verify_in: ReportVerifyRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_management)],
) -> Report:
    """Manajemen memverifikasi laporan: Approve, Reject, atau Minta Revisi."""
    result = await db.execute(
        select(Report)
        .options(
            selectinload(Report.items).joinedload(ReportItem.product),
            selectinload(Report.proofs),
            selectinload(Report.freelancer),
        )
        .where(Report.id == report_id)
    )
    report = result.scalar_one_or_none()
    if not report:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Laporan dengan ID {report_id} tidak ditemukan.",
        )

    # Validasi alasan revisi/penolakan
    if verify_in.status in (ReportStatus.REVISION, ReportStatus.REJECTED):
        if not verify_in.revision_notes or not verify_in.revision_notes.strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Catatan alasan wajib diisi jika status '{verify_in.status.value}'.",
            )

    report.status = verify_in.status
    report.revision_notes = verify_in.revision_notes

    await db.commit()
    await db.refresh(report)
    return report


@router.put("/{report_id}/revision", response_model=ReportResponse)
async def submit_report_revision(
    report_id: int,
    revision_in: ReportRevisionUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_freelancer)],
) -> Report:
    """Freelancer memperbaiki laporan revisi dengan ID LAPORAN YANG SAMA."""
    result = await db.execute(
        select(Report)
        .options(
            selectinload(Report.items),
            selectinload(Report.proofs),
            selectinload(Report.freelancer),
        )
        .where(Report.id == report_id)
    )
    report = result.scalar_one_or_none()
    if not report:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Laporan dengan ID {report_id} tidak ditemukan.",
        )

    # Validasi kepemilikan
    if report.freelancer_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Akses ditolak. Anda tidak berhak mengubah laporan ini.",
        )

    # Hanya laporan berstatus REVISION yang boleh diperbaiki
    if report.status != ReportStatus.REVISION:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Hanya laporan berstatus 'revision' yang dapat diperbaiki. Status saat ini: '{report.status.value}'.",
        )

    # Hitung ulang total botol & omzet
    (
        total_bottles,
        total_omzet,
        commission,
        management_share,
        computed_items,
    ) = await _calculate_report_totals(revision_in.items, db)

    # Hapus item lama
    for old_item in list(report.items):
        await db.delete(old_item)

    # Tambah item baru
    for item_data in computed_items:
        new_item = ReportItem(
            report_id=report.id,
            product_id=item_data["product_id"],
            quantity=item_data["quantity"],
            unit_price=item_data["unit_price"],
            subtotal=item_data["subtotal"],
        )
        db.add(new_item)

    # Perbarui data laporan dan kembalikan status ke PENDING untuk dicek ulang oleh manajemen
    report.total_bottles = total_bottles
    report.total_omzet = total_omzet
    report.commission_amount = commission
    report.management_share = management_share
    report.status = ReportStatus.PENDING
    report.revision_notes = f"[Direvisi oleh Freelancer pada {datetime.now(UTC).strftime('%Y-%m-%d %H:%M:%S')}] {report.revision_notes or ''}".strip()

    await db.commit()

    # Re-fetch hasil akhir
    refreshed = await db.execute(
        select(Report)
        .options(
            selectinload(Report.items).joinedload(ReportItem.product),
            selectinload(Report.proofs),
            selectinload(Report.freelancer),
        )
        .where(Report.id == report.id)
    )
    return refreshed.scalar_one()
