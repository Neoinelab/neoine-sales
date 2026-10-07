"""ORM 모델. 도메인 엔티티와 분리되어 있으며 변환은 각 Repository가 맡는다."""

from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.infra.db.base import Base


class AuditColumns:
    """모든 테이블 공통: 식별자, 생성·수정 시각, 소프트 삭제 표시."""

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)


class CustomerRow(AuditColumns, Base):
    __tablename__ = "customers"

    company_name: Mapped[str] = mapped_column(String(200))
    contact_name: Mapped[str] = mapped_column(String(100))
    contact_title: Mapped[str | None] = mapped_column(String(100), default=None)
    email: Mapped[str | None] = mapped_column(String(254), default=None)
    phone: Mapped[str | None] = mapped_column(String(40), default=None)
    employee_count: Mapped[int | None] = mapped_column(Integer, default=None)
    notes: Mapped[str] = mapped_column(String(2000), default="")

    __table_args__ = (
        CheckConstraint(
            "employee_count is null or employee_count >= 0", name="employee_count_non_negative"
        ),
        Index("ix_customers_created_at_id", "created_at", "id"),
    )


class PartnerRow(AuditColumns, Base):
    __tablename__ = "partners"

    company_name: Mapped[str] = mapped_column(String(200))
    contact_name: Mapped[str] = mapped_column(String(100))
    contact_title: Mapped[str | None] = mapped_column(String(100), default=None)
    email: Mapped[str | None] = mapped_column(String(254), default=None)
    phone: Mapped[str | None] = mapped_column(String(40), default=None)

    __table_args__ = (Index("ix_partners_created_at_id", "created_at", "id"),)


class DealRow(AuditColumns, Base):
    __tablename__ = "deals"

    code: Mapped[str] = mapped_column(String(50))
    name: Mapped[str] = mapped_column(String(200))
    owner: Mapped[str] = mapped_column(String(100))
    vendor: Mapped[str] = mapped_column(String(100))
    solution: Mapped[str] = mapped_column(String(200))
    revenue_amount: Mapped[Decimal] = mapped_column(Numeric(20, 4))
    revenue_currency: Mapped[str] = mapped_column(String(3))
    revenue_date: Mapped[date] = mapped_column(Date)
    customer_id: Mapped[UUID] = mapped_column(ForeignKey("customers.id", ondelete="RESTRICT"))
    partner_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("partners.id", ondelete="RESTRICT"), default=None
    )

    __table_args__ = (
        UniqueConstraint("code"),
        CheckConstraint("revenue_amount >= 0", name="revenue_non_negative"),
        Index("ix_deals_created_at_id", "created_at", "id"),
        Index("ix_deals_customer_id", "customer_id"),
        Index("ix_deals_partner_id", "partner_id"),
    )
