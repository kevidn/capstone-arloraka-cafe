import enum
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.product import Product
    from app.models.proof import Proof
    from app.models.user import User


class ReportStatus(enum.StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    REVISION = "revision"


class Report(Base, TimestampMixin):
    __tablename__ = "reports"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    freelancer_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    report_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )
    source_transaction_id: Mapped[str | None] = mapped_column(
        String(50), unique=True, index=True, nullable=True
    )
    payment_method: Mapped[str | None] = mapped_column(String(50), nullable=True)
    sale_location: Mapped[str | None] = mapped_column(String(150), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[ReportStatus] = mapped_column(
        Enum(ReportStatus, native_enum=False),
        default=ReportStatus.PENDING,
        nullable=False,
        index=True,
    )
    revision_notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Computed financial values
    total_bottles: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_omzet: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    commission_amount: Mapped[int] = mapped_column(
        Integer, default=0, nullable=False
    )  # 10% ceiling
    management_share: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # AI Anomaly Detection hook (ready for AI Engineer integration)
    is_flagged_anomaly: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )
    anomaly_reason: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Relationships
    freelancer: Mapped["User"] = relationship("User", back_populates="reports")
    items: Mapped[list["ReportItem"]] = relationship(
        "ReportItem",
        back_populates="report",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    proofs: Mapped[list["Proof"]] = relationship(
        "Proof",
        back_populates="report",
        cascade="all, delete-orphan",
        lazy="selectin",
    )


class ReportItem(Base, TimestampMixin):
    __tablename__ = "report_items"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    report_id: Mapped[int] = mapped_column(
        ForeignKey("reports.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    product_id: Mapped[int] = mapped_column(
        ForeignKey("products.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    unit_price: Mapped[int] = mapped_column(Integer, nullable=False)
    subtotal: Mapped[int] = mapped_column(Integer, nullable=False)

    # Relationships
    report: Mapped["Report"] = relationship("Report", back_populates="items")
    product: Mapped["Product"] = relationship("Product", lazy="joined")
